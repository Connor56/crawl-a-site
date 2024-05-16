# Overview

Crawl a Site is a full stack web application that lets you crawl a domain from
an initial starting point up to a maximum link depth. The project uses session
keys and Server Sent Events to update the client as the crawl progresses.

The tech stack is:

- FastAPI and Python for the backend.
- Nginx as the web server and reverse proxy.
- React and javascript as the frontend.

# How to run using Docker

These instructions assume you have the following packages installed:

- git, [download here](https://git-scm.com/downloads)
- Docker Desktop, [download here](https://www.docker.com/products/docker-desktop/)
- Node, [download here](https://nodejs.org/en/download/package-manager)

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

cd into the project:

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

Run the command below, if you'd like to use a different name for the
image, replace `crawler_backend` with your preferred name.

```bash
docker build -f Dockerfile.crawlerBackend -t crawler_backend .
```
