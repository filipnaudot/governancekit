#!/usr/bin/env bash
# Rebuild the Docker image from scratch and start a fresh container.
# Usage: ./rebuild.sh
# GK_ADMIN_SECRET and GK_JWT_SECRET are loaded from .env if it exists (see
# .env.example) and passed to the container. If they are not set, the server
# generates them and prints the admin secret in its logs.

set -euo pipefail

IMAGE="governancekit"
CONTAINER="gk"
PORT=8000

# Always run from the repo root (where this script and the Dockerfile live)
cd "$(dirname "$0")"

if [ -f .env ]; then
    echo "==> Loading secrets from .env"
    set -a  # export every variable .env defines
    source .env
    set +a
fi

echo "==> Removing old container '$CONTAINER' (if any)"
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

echo "==> Removing old image '$IMAGE' (if any)"
docker rmi -f "$IMAGE" >/dev/null 2>&1 || true

echo "==> Building image '$IMAGE'"
docker build -t "$IMAGE" .

echo "==> Starting container '$CONTAINER' on port $PORT"
docker run -d --name "$CONTAINER" -p "$PORT:8000" \
    -e GK_ADMIN_SECRET -e GK_JWT_SECRET "$IMAGE" >/dev/null

echo "==> Waiting for server to respond"
for _ in $(seq 1 20); do
    if curl -sf "http://localhost:$PORT/docs" >/dev/null; then
        echo "==> Server is up: http://localhost:$PORT/docs"
        echo "    Logs:  docker logs -f $CONTAINER"
        echo "    Stop:  docker stop $CONTAINER"
        exit 0
    fi
    sleep 0.5
done

echo "!! Server did not respond. Container logs:"
docker logs "$CONTAINER"
exit 1
