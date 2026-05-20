#!/usr/bin/env bash
set -euo pipefail

# Meatapivot Local Deployment Script
# Usage:
#   ./scripts/deploy-local.sh [up|down|restart|status|logs|build|ps]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.deploy.yml"
ENV_FILE="$PROJECT_DIR/.env.deploy"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }

check_prerequisites() {
    local missing=0
    for cmd in docker docker-compose; do
        if ! command -v "$cmd" &>/dev/null; then
            error "$cmd is not installed"
            missing=1
        fi
    done
    if [[ $missing -eq 1 ]]; then
        exit 1
    fi
}

check_env_file() {
    if [[ ! -f "$ENV_FILE" ]]; then
        warn "No .env.deploy found, copying from .env.example"
        if [[ -f "$PROJECT_DIR/.env.example" ]]; then
            cp "$PROJECT_DIR/.env.example" "$ENV_FILE"
        else
            error "No .env.example found either"
            exit 1
        fi
    fi
}

cmd_up() {
    info "Starting Meatapivot local deployment..."
    check_env_file
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
    success "All services started"
    echo ""
    info "Service URLs:"
    echo "  Frontend:    http://localhost:3000"
    echo "  Backend API: http://localhost:8000"
    echo "  API Docs:    http://localhost:8000/docs"
    echo "  Neo4j:       http://localhost:7474"
    echo "  MinIO:       http://localhost:9001"
    echo "  RabbitMQ:    http://localhost:15672"
    echo "  Keycloak:    http://localhost:8080"
    echo "  One API:     http://localhost:3005"
    echo "  Grafana:     http://localhost:3001"
    echo "  Prometheus:  http://localhost:9090"
    echo ""
    info "Run '$0 status' to check service health"
}

cmd_down() {
    info "Stopping all services..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
    success "All services stopped"
}

cmd_restart() {
    info "Restarting services..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart
    success "Services restarted"
}

cmd_status() {
    info "Service status:"
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
}

cmd_logs() {
    local service="${1:-}"
    if [[ -n "$service" ]]; then
        docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f "$service"
    else
        docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f --tail=100
    fi
}

cmd_build() {
    info "Building images..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache
    success "Images built"
}

cmd_ps() {
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
}

cmd_health() {
    info "Checking service health..."
    local services=(
        "http://localhost:8000/health|Backend API"
        "http://localhost:3000|Frontend"
        "http://localhost:7474|Neo4j"
        "http://localhost:9000/minio/health/live|MinIO"
        "http://localhost:9090/-/healthy|Prometheus"
        "http://localhost:3001/api/health|Grafana"
    )
    for entry in "${services[@]}"; do
        IFS='|' read -r url name <<< "$entry"
        if curl -sf --max-time 5 "$url" &>/dev/null; then
            success "$name ($url) - healthy"
        else
            warn "$name ($url) - not ready"
        fi
    done
}

cmd_clean() {
    warn "This will remove all containers, volumes, and images"
    read -rp "Are you sure? (y/N) " confirm
    if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
        docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v --rmi all
        success "Cleaned up"
    else
        info "Cancelled"
    fi
}

usage() {
    echo "Meatapivot Local Deployment Script"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  up          Build and start all services"
    echo "  down        Stop all services"
    echo "  restart     Restart all services"
    echo "  status      Show service status"
    echo "  logs [svc]  Show logs (optionally filter by service)"
    echo "  build       Rebuild images"
    echo "  ps          List running containers"
    echo "  health      Check service health"
    echo "  clean       Remove all containers, volumes, and images"
    echo ""
    echo "Examples:"
    echo "  $0 up                    # Start all services"
    echo "  $0 logs backend          # Show backend logs"
    echo "  $0 health                # Check all services"
}

check_prerequisites

case "${1:-}" in
    up)       cmd_up ;;
    down)     cmd_down ;;
    restart)  cmd_restart ;;
    status)   cmd_status ;;
    logs)     cmd_logs "${2:-}" ;;
    build)    cmd_build ;;
    ps)       cmd_ps ;;
    health)   cmd_health ;;
    clean)    cmd_clean ;;
    *)        usage ;;
esac
