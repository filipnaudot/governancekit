#!/usr/bin/env bash
# Rebuild the API and the frontend from scratch and start fresh containers.
# Usage: ./rebuild.sh
# GK_ADMIN_SECRET and GK_JWT_SECRET are loaded from .env if it exists (see
# .env.example) and passed to the API container. If they are not set, the
# server generates them and prints the admin secret in its logs.
# The frontend is the production build from compose.yaml; for hot reload use
#   docker compose -f compose.yaml -f compose.dev.yaml up --build

set -euo pipefail

IMAGE="governancekit"
CONTAINER="gk"
PORT=8000
FRONTEND_PORT=3000

# Always run from the repo root (where this script and the Dockerfile live)
cd "$(dirname "$0")"

# wait_for NAME URL: wait until URL responds, return 1 if it never does
wait_for() {
    echo "==> Waiting for $1 to respond"
    for _ in $(seq 1 20); do
        if curl -sf "$2" >/dev/null; then
            return 0
        fi
        sleep 0.5
    done
    return 1
}

if [ -f .env ]; then
    echo "==> Loading secrets from .env"
    set -a  # export every variable .env defines
    source .env
    set +a
fi

# --- API ---

echo "==> Removing old container '$CONTAINER' (if any)"
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

echo "==> Removing old image '$IMAGE' (if any)"
docker rmi -f "$IMAGE" >/dev/null 2>&1 || true

echo "==> Building image '$IMAGE'"
docker build -t "$IMAGE" .

echo "==> Starting container '$CONTAINER' on port $PORT"
docker run -d --name "$CONTAINER" -p "$PORT:8000" \
    -e GK_ADMIN_SECRET -e GK_JWT_SECRET "$IMAGE" >/dev/null

if ! wait_for "API" "http://localhost:$PORT/docs"; then
    echo "!! API did not respond. Container logs:"
    docker logs "$CONTAINER"
    exit 1
fi

# --- Frontend ---

echo "==> Removing old frontend container (if any)"
docker compose down --remove-orphans >/dev/null 2>&1 || true

echo "==> Building and starting the frontend on port $FRONTEND_PORT"
docker compose up --build -d

if ! wait_for "frontend" "http://localhost:$FRONTEND_PORT"; then
    echo "!! Frontend did not respond. Container logs:"
    docker compose logs frontend
    exit 1
fi

echo
echo "==> API is up:      http://localhost:$PORT/docs"
echo "    Logs:  docker logs -f $CONTAINER"
echo "    Stop:  docker stop $CONTAINER"
echo "==> Frontend is up: http://localhost:$FRONTEND_PORT"
echo "    Logs:  docker compose logs -f frontend"
echo "    Stop:  docker compose down"
