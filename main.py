import uuid
import asyncio
from contextlib import asynccontextmanager
import json
from typing import Dict, Union
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
import httpx


class Session(BaseModel):
    """
    Session information to setup the crawling session.
    """

    url: str
    max_depth: int = Field(default=1)


all_crawlers = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Provides an asynchronous context manager to handle the startup
    and shutdown phases of a FastAPI application. During the startup,
    this function performs no operations (yielding immediately), and
    upon shutdown, it manages the cleanup of all the asyncio tasks
    being run by the server.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance.

    Yields
    ------
    None
        Allows the FastAPI app to run within the context.

    Notes
    -----
    On exit from the context, the function cancels all asyncio tasks,
    typically crawlers or similar background tasks. It then waits for
    all these tasks to finish cancellation, ensuring a clean shutdown.
    This is critical for freeing up resources and avoiding potential
    memory leaks or unfinished transactions.
    """
    yield
    # Print all tasks (optional, for debug purposes)
    print(f"Cancelling {len(all_crawlers)} crawlers")
    # Cancel all tasks
    [crawler.cancel() for crawler in all_crawlers]
    # Wait until all tasks are cancelled
    await asyncio.gather(*all_crawlers, return_exceptions=True)
    print("Cancelled all crawlers.")


app = FastAPI(lifespan=lifespan)
# Setup a sessions dictionary to handle multiple users
sessions = {}
session_lock = asyncio.Lock()


@app.post("/set_session")
async def set_session(session: Session):
    """
    Initialises the session so the client can attach to an
    EventSource from the front end and be sent updates via SSE.

    A unique session key is generated for each user and used as the
    dictionary key.
    """
    """
    Handles the creation of a unique session for a client to
    facilitate Server-Sent Events (SSE). It initializes a session
    with a unique key, and begins a crawling task based on the
    session parameters.

    Parameters
    ----------
    session : Session
        The session object containing configuration details: `url`
        and `max_depth` for the web crawling task.

    Returns
    -------
    JSONResponse
        A response containing the unique session key in JSON format.

    Notes
    -----
    The function generates a unique session key for each user which
    acts as a dictionary key to store session details. It also
    asynchronously starts a web crawling task based on the session
    parameters. This setup is critical for enabling real-time updates
    to clients via SSE.
    """
    session_key = str(uuid.uuid4())
    async with session_lock:
        sessions[session_key] = {"url": session.url}
        asyncio.create_task(crawl(session_key, session.max_depth))
        return JSONResponse(content={"key": session_key})


@app.get("/stop_session")
async def stop_session(session_key: str):
    """
    Terminates a web crawling session by pausing ongoing operations
    and clearing its task queue. This endpoint ensures that all
    resources allocated to the session are properly released.

    Parameters
    ----------
    session_key : str
        The unique identifier for the session to be stopped.

    Returns
    -------
    dict
        A confirmation message indicating the success of the
        operation.

    Notes
    -----
    This function first pauses the worker tasks associated with the
    session by clearing a synchronization flag (`run_flag`). It then
    awaits a brief delay to ensure all workers have ceased operations
    before draining the URL queue associated with the session. This
    method ensures that all pending tasks are acknowledged and
    cleaned, preventing any orphan tasks or resource leakage.
    """
    async with session_lock:
        url_queue = sessions[session_key]["url_queue"]
        run_flag = sessions[session_key]["run_flag"]
        # Pause the workers
        run_flag.clear()

    # Wait for all the workers to wait on the run flag
    await asyncio.sleep(2)

    while not url_queue.empty():
        item = url_queue.get_nowait()
        url_queue.task_done()
    print(f"Url Queue for Session: {session_key} has been drained.")
    return {"status": "Success"}


async def crawl(session_key: str, max_depth: int):
    """
    Orchestrates a web crawling session using asynchronous tasks that
    navigate and process URLs from a queue. It initializes various
    components required for the crawl, such as queues for URLs and
    messages, a set for visited URLs, and controls for task execution.

    Parameters
    ----------
    session_key : str
        The unique identifier for the session, used to manage and
        retrieve session-specific data such as the URL queue.

    max_depth : int
        The maximum depth to which the crawler should explore the
        website, from the initial url.

    Notes
    -----
    This function is a core part of initiating and managing an
    asynchronous web crawling session. Multiple crawler tasks are
    spawned to handle the URLs concurrently. It produces the crawlers
    shared scope, allowing them to work in tandem. When all the tasks
    are complete it cleanly terminates the crawlers.
    """
    print(f"Crawl with ID: {session_key} has begun.")

    # Set the configurations for the crawl
    max_crawlers = 2
    max_attempts = 8
    min_wait = 0.1  # seconds

    # Build asynchronous objects for crawl
    url_queue = asyncio.Queue()
    run_flag = asyncio.Event()
    run_flag.set()
    visited = set()
    visited_lock = asyncio.Lock()
    message_queue = asyncio.Queue()
    backoff = {
        "wait": 0.25,
        "consecutive_failures": 0,
    }
    backoff_lock = asyncio.Lock()

    # Record session data to share across endpoints
    async with session_lock:
        sessions[session_key]["message_queue"] = message_queue
        sessions[session_key]["url_queue"] = url_queue
        sessions[session_key]["run_flag"] = run_flag

    # Begin the queue with the initial url
    base_url = sessions[session_key]["url"]
    start_url = {"url": base_url, "depth": 0}
    await url_queue.put(start_url)
    workers = [
        asyncio.create_task(
            crawler(
                base_url,
                url_queue,
                visited,
                visited_lock,
                message_queue,
                max_depth,
                backoff,
                backoff_lock,
                max_attempts,
                min_wait,
                run_flag,
            )
        )
        for _ in range(max_crawlers)
    ]

    # Wait for the queue to empty
    global all_crawlers
    all_crawlers += workers
    await url_queue.join()
    print("End of Queue.")

    # Clean up the workers
    print(f"Cancelling {len(workers)} crawlers.")
    for worker in workers:
        worker.cancel()
    await asyncio.gather(*workers, return_exceptions=True)
    print(f"Cancelled 2 crawlers.")
    print(f"Crawl with ID: {session_key} has ended.")


async def crawler(
    base_url: str,
    url_queue: asyncio.Queue,
    visited: set,
    visited_lock: asyncio.Lock,
    message_queue: asyncio.Queue,
    max_depth: int,
    backoff: Dict[str, Union[int, float]],
    backoff_lock: asyncio.Lock,
    max_attempts: int,
    min_wait: float,
    run_flag: asyncio.Event,
):
    """
    Executes the web crawling logic asynchronously by working through
    a queue of URLs, applying depth and attempt constraints, and
    handling HTTP requests with retries and backoff strategies. The
    function sends data back to clients via a message queue.

    Parameters
    ----------
    base_url : str
        The root URL from which the crawling begins, used to filter
        outbound links.

    url_queue : asyncio.Queue
        The queue that holds URLs to be crawled, structured with URL
        and depth.

    visited : set
        A set to record URLs that have been visited to avoid
        revisiting them.

    visited_lock : asyncio.Lock
        A lock to ensure safe modification of the visited set.

    message_queue : asyncio.Queue
        The queue used for sending back information about crawled
        URLs.

    max_depth : int
        The maximum depth to crawl beyond which URLs are ignored.

    backoff : Dict[str, Union[int, float]]
        A crawler shared dictionary managing the backoff strategy for
        retries, with parameters like wait time and consecutive
        failure count.

    backoff_lock : asyncio.Lock
        A lock to ensure safe access to the backoff dictionary.

    max_attempts : int
        The maximum number of attempts to fetch a URL before giving
        up.

    min_wait : float
        The minimum wait time between HTTP requests to manage server
        load.

    run_flag : asyncio.Event
        A shared flag to control the running state of all crawlers in
        a session, allowing for a global pause and resume
        functionality.

    Notes
    -----
    This function leverages the httpx.AsyncClient for asynchronous
    HTTP requests, handling responses, and parsing links within web
    pages using BeautifulSoup. Errors and backoff are managed based
    on HTTP response status. The crawler adjusts its behavior
    dynamically based on errors encountered, such as backing off on
    receiving 429 Too Many Requests or server errors.
    """
    async with httpx.AsyncClient() as client:
        while True:
            # Pause run if the flag is cleared
            await run_flag.wait()
            next_url = await url_queue.get()

            # Skip urls above the maximum search depth
            depth = next_url["depth"]
            if depth > max_depth:
                url_queue.task_done()
                print(f"Over Max Depth: {depth}")
                continue

            url = next_url["url"]
            # Skip urls that have already been visited
            async with visited_lock:
                if url in visited:
                    print("Already seen URL.")
                    url_queue.task_done()
                    continue
                else:
                    visited.add(url)

            # Avoid overstressing servers
            await asyncio.sleep(min_wait)

            attempts = 0
            while True:

                if attempts > max_attempts:
                    url_queue.task_done()
                    print("Max attempts reached.")
                    break
                attempts += 1

                # Attempt to crawl the url
                try:
                    response = await client.get(url)
                    response.raise_for_status()

                    # Re-calculate back off if no errors raised
                    await backoff_calculator(
                        backoff,
                        backoff_lock,
                        failed=False,
                        min_wait=min_wait,
                    )

                    # Get the unvisited links
                    soup = BeautifulSoup(response.text, "html.parser")
                    links = {
                        a["href"]
                        for a in soup.find_all("a", href=True)
                        if a["href"].startswith(base_url)
                    }

                    # Queue a message for the data stream
                    await message_queue.put(
                        {"visited": url, "links": list(links), "depth": depth}
                    )

                    # Add links to the queue
                    async with visited_lock:
                        links = links - visited
                    for link in links:
                        await url_queue.put({"url": link, "depth": depth + 1})

                    url_queue.task_done()
                    break

                except httpx.HTTPStatusError as e:
                    print(
                        f"Request failed: {e.response.status_code} for URL: {url}"
                    )
                    # Page is inaccessible, skip
                    skip_codes = [301, 302, 400, 401, 403, 404]
                    # Page is accessible, but wait
                    backoff_codes = [429, 500, 502, 503, 504]
                    if e.response.status_code in skip_codes:
                        await message_queue.put(
                            {"visited": url, "links": [], "depth": depth}
                        )
                        url_queue.task_done()
                        break
                    elif e.response.status_code in backoff_codes:
                        wait_time = await backoff_calculator(
                            backoff,
                            backoff_lock,
                            failed=True,
                            min_wait=min_wait,
                        )
                        print("Backing Off")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"Unhandled Error Code: {e.response.status_code}")
                        break


async def backoff_calculator(
    backoff: Dict[str, Union[int, float]],
    backoff_lock: asyncio.Lock,
    failed: bool,
    min_wait: float,
) -> int:
    """
    Adjusts the wait time dynamically based on the success or failure
    of HTTP requests, employing an exponential backoff and decay
    strategy.

    Parameters
    ----------
    backoff : Dict[str, Union[int, float]]
        A dictionary holding the current wait time and the count of
        consecutive failures.

    backoff_lock : asyncio.Lock
        A lock to ensure exclusive access to the backoff dictionary
        during updates.

    failed : bool
        Indicates whether the most recent HTTP request failed.

    min_wait : float
        The minimum wait time that should be maintained after
        decaying.

    Returns
    -------
    int
        The updated wait time after adjustments.

    Notes
    -----
    If an operation fails, this function doubles the wait time and
    increments the count of consecutive failures. If the operation
    succeeds, it applies a decay factor to the wait time (reducing it
    by 20%) but not below the specified minimum wait time, resetting
    the failure count. This approach helps manage request rates
    adaptively.
    """
    async with backoff_lock:
        if failed:
            backoff["wait"] = backoff["wait"] * 2
            backoff["consecutive_failures"] += 1
        else:
            if backoff["wait"] > min_wait:
                backoff["wait"] = backoff["wait"] * 0.8
            backoff["consecutive_failures"] = 0

        return backoff["wait"]


@app.get("/data_stream")
async def data_stream(session_key: str):
    """
    A session key is provided by the client and used to connect to
    data stream that's generated by the crawl endpoint.

    The messages are streamed to the client as they come in from the
    crawlers.
    """
    """
    Streams live data back to the client using Server-Sent Events
    (SSE). This endpoint connects to a message queue for a given
    session and continuously transmits any messages received from
    the associated crawling process.

    Parameters
    ----------
    session_key : str
        The unique identifier for the client's session, used to
        retrieve the appropriate message queue for the data stream.

    Returns
    -------
    StreamingResponse
        An SSE stream that sends a continuous flow of messages in
        real-time, formatted as JSON data.

    Notes
    -----
    This function defines an asynchronous generator,
    `event_generator`, which listens for new messages from the
    message queue. Each message is formatted and sent as a data event
    in the SSE stream. This allows the client to receive live updates
    about the crawling progress and results.
    """
    print("hi")
    async with session_lock:
        message_queue = sessions[session_key]["message_queue"]

    async def event_generator():
        while True:
            message = await message_queue.get()
            yield f"data: {json.dumps(message)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=80)
