#!/bin/bash
# deploy.sh — Actualiza y redespliega TOOL_API en el VPS.
# Uso: bash deploy.sh
# Requisitos en el VPS: git, docker, docker compose v2

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="docker compose"

echo ">>> [1/5] Pulling latest changes from git..."
BRANCH="$(git -C "$APP_DIR" rev-parse --abbrev-ref HEAD)"
git -C "$APP_DIR" pull origin "$BRANCH"

echo ">>> [2/5] Verifying .env exists..."
if [ ! -f "$APP_DIR/.env" ]; then
    echo "ERROR: .env not found. Copy .env.example and fill in the values:"
    echo "  cp $APP_DIR/.env.example $APP_DIR/.env"
    exit 1
fi

echo ">>> [3/5] Building and restarting containers..."
$COMPOSE -f "$APP_DIR/docker-compose.yml" up --build -d --remove-orphans

echo ">>> [4/5] Removing unused images..."
docker image prune -f

echo ">>> [5/5] Checking container status..."
$COMPOSE -f "$APP_DIR/docker-compose.yml" ps

echo ""
echo "===================================="
echo " Deploy complete!"
echo " API running on http://$(hostname -I | awk '{print $1}'):5555"
echo " Health: http://$(hostname -I | awk '{print $1}'):5555/v1/health"
echo "===================================="
