# ReylAI independent container server

This folder is a standalone Linux container server that is independent from the main ReylAI app.

## Run locally

```sh
node server.js
```

## Build container

```sh
docker build -t reylai-container-server .
```

## Run container

```sh
docker run -p 3000:3000 reylai-container-server
```
