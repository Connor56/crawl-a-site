# Overview

Crawl a Site is a full stack web application that lets you crawl a
domain from an initial starting point up to a maximum link depth. The
project uses session keys and Server Sent Events to update the client
as the crawl progresses.

The tech stack is:

- FastAPI and Python for the backend.
- Nginx as the web server and reverse proxy.
- React and javascript as the frontend.

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

Navigate to your localhost by visiting the following url:

```
http://localhost
```

You'll be presented with the following interface:
