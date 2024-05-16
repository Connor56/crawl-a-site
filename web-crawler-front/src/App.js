import React, { useState } from "react";
import "./App.css";

function App() {
  const [url, setUrl] = useState("");
  const [maxDepth, setMaxDepth] = useState(2);
  const [started, setStarted] = useState(false);
  const [visited, setVisited] = useState([]);
  const [linkCounts, setLinkCounts] = useState({});
  const [linkPresentation, setLinkPresentation] = useState([]);
  const [sessionKey, setSessionKey] = useState("");

  const countLinks = (links) => {
    for (let link of links) {
      if (link in linkCounts) {
        linkCounts[link] += 1;
      } else {
        linkCounts[link] = 1;
      }
    }

    // Get all the items and then sort them by their count
    var items = Object.keys(linkCounts).map((key) => {
      return { url: key, count: linkCounts[key] };
    });
    items.sort((first, second) => {
      return second["count"] - first["count"];
    });

    setLinkPresentation(items);
  };

  const getStream = (sessionKey) => {
    setSessionKey(sessionKey);
    console.log("hi");
    const eventSource = new EventSource(
      `/api/data_stream?session_key=${sessionKey}`
    );

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      let link_visited = { visited: data.visited, depth: data.depth };
      let links = data.links;
      console.log(data);
      for (let link of links) {
        console.log(link);
      }
      setVisited((visited) => [...visited, link_visited]);
      countLinks(links);
    };

    eventSource.onerror = (error) => {
      console.error("EventSource failed:", error);
      eventSource.close();
    };
  };

  const handleCrawl = async () => {
    setStarted(true);
    const response = await fetch("/api/set_session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url: url, max_depth: maxDepth }),
    });
    const data = await response.json();
    console.log(data);
    getStream(data.key);
  };

  const handleBack = async () => {
    setStarted(false);
    await handleStop();
    console.log(visited);
    console.log(linkCounts);
    setVisited([]);
    setLinkCounts({});
    setLinkPresentation([]);
  };

  const handleStop = async () => {
    const response = await fetch(`/api/stop_session?session_key=${sessionKey}`);
    console.log(response);
  };

  return (
    <div className="App">
      {!started && (
        <>
          <h1 className="title">Crawl a Site</h1>
          <div className="input-area centered">
            <div className="stacked_box">
              <h2 className="front_header">URL</h2>
              <input
                type="text"
                className="url_holder_home"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="Enter URL to crawl"
                title="URLS must be given in full, for example: https://www.bbc.co.uk, instead of bbc.co.uk, or www.bbc.co.uk."
              />
            </div>
            <div className="stacked_box search_depth">
              <h2 className="front_header">Search Depth</h2>
              <input
                type="number"
                className="url_holder_home"
                min={0}
                max={100}
                value={maxDepth}
                onChange={(e) => setMaxDepth(e.target.value)}
                placeholder="Maximum Search Depth"
                title="The maximum number of links to follow before stopping."
              />
            </div>
            <button className="standard_button" onClick={handleCrawl}>
              Go
            </button>
          </div>
        </>
      )}
      {started && (
        <>
          <div className="container">
            <div className="box">
              <h1 className="box_title">Visited</h1>
              <ol>
                {visited.map((e, index) => (
                  <li>
                    <a className="white_link" href={e.visited} key={index}>
                      {e.visited}
                    </a>{" "}
                    - Depth: {e.depth}
                  </li>
                ))}
              </ol>
            </div>
            <div className="box">
              <h1 className="box_title">Link Leaderboard</h1>
              {linkPresentation.map((link, index) => (
                <div key={index}>
                  <p>
                    {link.count} -{" "}
                    <a className="white_link" href={link.url}>
                      {link.url}
                    </a>
                  </p>
                </div>
              ))}
            </div>
          </div>
          <div className="input-area bottom">
            <button
              className="standard_button stop_button"
              onClick={handleStop}
              title="Stop the crawl."
            >
              Stop
            </button>
            <div className="url_holder">{url}</div>
            <button
              className="standard_button"
              title="Stop the crawl and choose another URL."
              onClick={handleBack}
            >
              Back
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default App;
