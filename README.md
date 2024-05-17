# Overview

## Introduction

Crawl a Site is a full stack web application that lets you crawl a
domain from an initial starting point up to a maximum link depth. The
project uses session keys and Server Sent Events to update the client
as the crawl progresses.

The tech stack is:

- FastAPI, Python, and httpx for the backend.
- Nginx as the web server and reverse proxy.
- React and javascript as the frontend.

## Tech Stack Discussion

These were my focuses for the build:

1. Serve the frontend statically, and centre as much compute as possible on the client side.
2. Run multiple crawls concurrently.
3. Minimise data transfer between the server and the client.
4. Stream server updates in realtime.
5. Multiple workers for each crawl with a shared task queue.
6. Prevent exponential growth of work by limiting link depth.
7. Graceful shutdown of resources when a crawl is finished.
8. Manual shutdown of the crawl and its resources when required by the user.
9. Containerise the frontend and the backend separately so they can be horizontally scaled.
10. Prevent server overload with dynamic request timing.

### Frontend

I chose Nginx as my web server to help with points 1, 2, and 9. It's
lightweight and able to spread work across multiple backend servers
if necessary for horizontal scalability. It's also considered the best
in class web server for static files.

However, despite it's performance, S3 and CloudFront would outperform
it, which led to my first trade off. I opted to design my stack
so that it could be deployed in the cloud, but not be tied to the
cloud. I did this to keep my application platform agnostic, and my
code faster to develop. As the application is in an alpha stage, I
didn't consider the time and money investment required for
cloud deployment worthwhile.

I used a React frontend because this application has a small frontend
and a large, high-compute backend. Therefore, the potential extra
costs of data transfer due to minified react being larger than other
frameworks like Svelte is minimal. In terms of speed, the project
is small, and it's unlikely there would be a noticeable UX benefit
from using a faster framework, so I chose the framework I know best.
This is technically a trade off between performance and development
speed, but in my opinion an insignificant one.

### Backend

I built my backend server using Asycnhronous functions and FastAPI. I
chose FastAPI because it's the fastest, lightest weight Python
application server available. I limited myself to Python frameworks
because time constraints meant I had to focus on what I knew best.
This was the biggest trade off I made in the tech stack, development
speed for backend performance. If I had more time, I would have
explored the available frameworks in Go, for example Fibre and Echo.
This is rational trade off because it allowed me to develop the
features I was asked to, and provides a good benchmark and
scaffold to build from.

One of foreseeable downsides of using a low performance framework is
the potential for worker slow downs because of data transfer. To get
data transfer as low as possible, I setup a message queue that
streams small updates with information every time a site is
visited, and placed the sitemap building logic on the client side.
Keeping expensive computation on the client side increases the
throughput of the backend, and lowers costs.

The asynchronous design of the API allows multiple crawl processes to
be run at the same time. Each process is assigned a session ID and
session details that allow the client to interact with the process
after its begun. Within each crawl session, an `asyncio.Queue` is
shared among the crawlers, which spreads the work across them both
equally. Similarly, because the crawlers are crawling the same root
domain, a joint object for backoff is shared between them and used to
coordinate wait times. The backoff time is updated every time a
request succeeds or fails.

The crawlers associated with a crawling session are tracked and when
the `asyncio.Queue` has emptied they're shutdown gracefully. A run
flag is also passed to the crawlers, which can be cleared by the client
to pause them. The queue can then be drained, and the crawl session
will automatically end.

I containerised the whole application in Docker to meet horizontal
scaling requirements, and make it easier for a potential client to
deploy.

All testing completed on this project was manual, as it involved
a lot of exploratory work. This resulted in a trade off between early
development speed and stability + solid performance metrics + later
development speed. For a full-stack potentially high throughput
solution, I believe metrics is what this project lacks the most, and
that would be my immediate next focus. I would use the metrics to
plan a beta build, with deeper testing, telemetry data in the UI, and
the ability to deploy to the cloud.

# How to run using Docker

## Before you begin

These instructions assume you have the following packages installed:

- `Git`, [download here](https://git-scm.com/downloads)
- `Docker Desktop`, [download here](https://www.docker.com/products/docker-desktop/)
- `Node`, [download here](https://nodejs.org/en/download/package-manager)

They also assume that you're able to work with a command line shell.
For example:

- [Powershell](https://en.wikipedia.org/wiki/PowerShell),
- [zsh](https://en.wikipedia.org/wiki/Z_shell),

### Warning

These instructions have only been tested in Windows on Docker
for [Windows Subsystem for Linx 2 (wsl2)](https://learn.microsoft.com/en-us/windows/wsl/install).
It's probable they will work on MacOS, but because nginx is using
the `host.docker.internal` variable to proxy pass requests it may fail on
Linux.

If you have a Linux machine, and you find that the app is returning
"`404 resource not found", go to the `crawl-a-site` root
directory and look in the following file:

```bash
nginx/conf/nginx.conf
```

Go to the FastAPI server proxy pass section:

```nginx
# Proxy API requests to the FastAPI server
location /api/ {
    proxy_pass http://host.docker.internal:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off; # Ensure real-time updates are sent immediately
}
```

This passes traffic from `localhost/api` of the nginx container to
host port 8000. But the `host.docker.internal` may be specific to
Windows and MacOS. If this is the case, alter this so that the
networking works on your Linux system.

## Clone the package to your local machine

Run one of the following commands:

### SSH

```bash
git clone https://github.com/Connor56/crawl-a-site
```

### HTTPS

```bash
https://github.com/Connor56/crawl-a-site.git
```

## Build the Docker images

Enter the project:

```bash
cd crawl-a-site
```

### Build the backend

Run the command below, if you'd like to use a different name for the
image, replace `crawler_backend` with your preferred name.

```bash
docker build -f Dockerfile.crawlerBackend -t crawler_backend .
```

### Build the frontend

The frontend react app is served as static files by [Nginx](https://nginx.org/en/),
which need to built before the Docker file can run. To build the
react app, enter the `web-crawler-front` directory:

```bash
cd web-crawler-front
```

From here install all of the node packages for the project with the
following command:

```bash
npm install
```

Now build the react app:

```bash
npm run build
```

You should now see a build folder in your web-crawler-front directory.
This directory includes the static files that will be served by nginx.
With the build directory prepared, move back up a directory:

```bash
cd ..
```

and run the following docker command:

```bash
docker build -f Dockerfile.frontendServer -t crawler_frontend .
```

If you'd like to use a different name for the
image, replace `crawler_frontend` with your preferred name.

## Run the containers

Setup the containers using the following commands:

```bash
docker run -d -p 8000:80 --name crawler_backend_container crawler_backend
```

```bash
docker run -d -p 80:80 --name crawler_frontend_container crawler_frontend
```

If you chose different names for the images, you need replace the
final argument, which is the image name, with your chosen image
names.

### Docker run tips

The Docker run command above uses three flags:

- `-d`, which means "detach" and allows your container to run without blocking your shell.
- `-p`, which means "publish" and lets you publish a container's ports to the host using the following syntax `[host-port]:[contaier-port]`. In other words, if you want your localhost port 8000 to point to the containers port 80, you use `-p 8000:80`.
- `--name`, which gives a name to your container making it easier to track.

## Use the application

Navigate to your localhost by visiting the following URL:

[`http://localhost`](HTTP://localhost)

You'll be presented with the following interface:

![image](https://github.com/Connor56/crawl-a-site/assets/34070858/67648142-4d6f-49a3-8cfe-1e789ac2f6d8)

Enter an url that you'd like to crawl. Because this application is in an
alpha stage your url must be precise. You must include the protocol you'd
like to use, e.g. `http` or `https`, and the prefix `www.`. These will not be
autocompleted for you, and incorrect input will result in the crawl failing.

Once you've chosen your url, select your search depth, the maximum number
of link hops you're willing to travel from your main site. This parameter
controls how long your search takes, and can help prevent your IP being blocked
by your chosen site.

Once you're done hit `Go`.

### The bbc.co.uk as an example

I can choose my url to be `https://www.bbc.co.uk`, set my depth to 3 and
hit Go:

![image](https://github.com/Connor56/crawl-a-site/assets/34070858/e7c63896-ea96-4952-9182-41be81bbfe4b)

I get taken to the following screen:

![image](https://github.com/Connor56/crawl-a-site/assets/34070858/81938311-af26-4fec-bedc-a50df989edb1)

This screen updates in real-time with the URLs that have been visited
and in what order in the left-hand pane, and the most linked URLs in
the right-hand pane.

If you're like me and paranoid about getting your IP banned, you can halt
the crawl by pressing the stop button. Currently, this ends your crawling
session but leaves your crawl's data in the UI for you to peruse.

The back button performs a similar function, except it also returns you
to the home screen where you can enter a different URL or change your
search depth.
