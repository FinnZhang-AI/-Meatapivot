#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"

ENVIRONMENT="${1:-dev}"
PROFILE="${2:-}"

echo "========================================="
echo "Deploying Knowledge Platform via Docker Compose"
echo "Environment: ${ENVIRONMENT}"
echo "========================================="

cd "${PROJECT_ROOT}"

# Export environment for compose
export COMPOSE_PROFILES="${PROFILE}"

# Pull latest images if in staging/prod
if [[ "${ENVIRONMENT}" != "dev" ]]; then
  echo "Pulling latest images..."
  docker-compose -f "${COMPOSE_FILE}" pull
fi

# Start services
echo "Starting services..."
docker-compose -f "${COMPOSE_FILE}" up -d --remove-orphans

# Health check
echo "Waiting for services to be healthy..."
sleep 10

docker-compose -f "${COMPOSE_FILE}" ps

echo "========================================="
echo "Docker Compose deployment completed!"
echo "Services:"
echo "  Frontend:  http://localhost:3000"
echo "  Backend:   http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Grafana:   http://localhost:3001"
echo "  Prometheus: http://localhost:9090"
echo "========================================="
