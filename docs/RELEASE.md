# Meatapivot v2.2 — Release & Deployment Guide

> Production deployment guide for Meatapivot v2.2.0

## Table of Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Quick Start (Docker Compose)](#quick-start-docker-compose)
- [Production Hardening](#production-hardening)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Monitoring & Alerting](#monitoring--alerting)
- [Backup & Recovery](#backup--recovery)
- [Troubleshooting](#troubleshooting)

---

## Overview

Meatapivot v2.2 is a multi-tenant enterprise knowledge management platform with
the following stack:

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0 (async) | API + business logic |
| Frontend | React 18, TypeScript, Vite, TailwindCSS | UI |
| Database | PostgreSQL 15 | Primary data store |
| Graph DB | Neo4j 5.15 | Knowledge graph |
| Cache | Redis 7 | Schema registry, sessions |
| Object Storage | MinIO | Documents, file uploads |
| Vector DB | Milvus 2.3.6 | Semantic search |
| Message Queue | RabbitMQ 3.12 | Async tasks |
| Auth | Keycloak 23 | OIDC SSO |
| Proxy | Nginx | API gateway |
| Observability | Prometheus + Grafana + Loki + Tempo | Monitoring |

---

## System Requirements

### Minimum (Single-node, dev/staging)

- **CPU**: 4 cores
- **RAM**: 16 GB
- **Disk**: 100 GB SSD
- **OS**: Linux (Ubuntu 22.04+) / macOS 12+
- **Docker**: 24.0+
- **Docker Compose**: 2.20+

### Recommended (Production)

- **CPU**: 16+ cores
- **RAM**: 64 GB
- **Disk**: 500 GB NVMe SSD
- **OS**: Ubuntu 22.04 LTS
- **Docker**: 24.0+
- **Kubernetes**: 1.28+ (for HA deployment)

### Network Ports

| Port | Service | Public? |
|------|---------|---------|
| 80 | Nginx (HTTP) | Yes (redirect to 443) |
| 443 | Nginx (HTTPS) | Yes |
| 5432 | PostgreSQL | No (internal only) |
| 6379 | Redis | No |
| 7474, 7687 | Neo4j | No |
| 8080 | Keycloak | Optional (OIDC redirect) |
| 9000, 9001 | MinIO | No |
| 9090 | Prometheus | No (or via Nginx) |
| 3001 | Grafana | Optional (via Nginx) |

---

## Pre-Deployment Checklist

### 1. Secrets Rotation

- [ ] Generate new `JWT_SECRET_KEY` (min 64 chars):
  ```bash
  openssl rand -hex 32
  ```
- [ ] Generate new database password:
  ```bash
  openssl rand -base64 24
  ```
- [ ] Generate new MinIO root credentials
- [ ] Generate new Keycloak admin password
- [ ] Generate new Redis password
- [ ] Generate new Neo4j password

### 2. Environment Configuration

Create `.env` from template:
```bash
cp .env.example .env
# Edit .env with production values
chmod 600 .env
```

### 3. TLS Certificates

Obtain certificates (Let's Encrypt recommended):
```bash
# Install certbot
sudo apt install certbot
sudo certbot certonly --standalone -d yourdomain.com
```

### 4. DNS Configuration

Point your domain to the server:
- `yourdomain.com` → Server IP
- `*.yourdomain.com` → Server IP (if using subdomains)

---

## Quick Start (Docker Compose)

### 1. Clone the repository

```bash
git clone https://github.com/yourorg/Meatapivot.git
cd Meatapivot
git checkout v2.2.0
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env
nano .env
```

### 3. Start the stack

```bash
# Pull images
docker-compose pull

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# Tail logs
docker-compose logs -f backend
```

### 4. Run database migrations

```bash
docker-compose exec backend alembic upgrade head
```

### 5. Create admin user

```bash
# Register admin
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@yourdomain.com",
    "password": "CHANGE_ME",
    "name": "Admin",
    "tenant_id": "00000000-0000-0000-0000-000000000001"
  }'
```

### 6. Verify

```bash
# Health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs

# Grafana (optional)
open http://localhost:3001
# Default: admin / admin (change immediately!)
```

---

## Production Hardening

### 1. Disable Debug Mode

`.env`:
```bash
DEBUG=False
```

### 2. Restrict CORS

`.env`:
```bash
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

### 3. Configure Rate Limiting

`docker/nginx/nginx.conf` already includes:
- `api` zone: 10 req/s, burst 50
- `auth` zone: 5 req/s, burst 10

### 4. Enable HTTPS

Create `/docker/nginx/ssl.conf`:
```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/ssl/certs/yourdomain.com.crt;
    ssl_certificate_key /etc/ssl/private/yourdomain.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # ... rest of config
}

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}
```

### 5. Database Backups

Set up automated daily backups:
```bash
# /etc/cron.daily/Meatapivot-backup
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/var/backups/Meatapivot
mkdir -p $BACKUP_DIR

# PostgreSQL
docker-compose exec -T postgres pg_dump -U knowledge knowledge_db \
  | gzip > $BACKUP_DIR/postgres_$TIMESTAMP.sql.gz

# Neo4j
docker-compose exec -T neo4j neo4j-admin dump \
  --database=neo4j --to=/var/lib/neo4j/backup/neo4j_$TIMESTAMP.dump

# MinIO (via mc client)
mc mirror minio/Meatapivot $BACKUP_DIR/minio_$TIMESTAMP/

# Retention: 7 daily, 4 weekly, 6 monthly
find $BACKUP_DIR -mtime +7 -delete
```

### 6. Log Rotation

`/etc/logrotate.d/Meatapivot`:
```
/var/log/Meatapivot/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        docker-compose restart backend
    endscript
}
```

### 7. Security Headers

In `docker/nginx/nginx.conf`:
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Content-Security-Policy "default-src 'self';" always;
```

### 8. Firewall Rules

```bash
# Allow only necessary ports
sudo ufw default deny incoming
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

---

## Kubernetes Deployment

For HA deployment, use Kubernetes manifests in `deploy/k8s/`:

```bash
# Create namespace
kubectl apply -f deploy/k8s/00-namespace.yaml

# Create secrets
kubectl create secret generic meatapivot-secrets \
  --from-literal=jwt-secret=$(openssl rand -hex 32) \
  --from-literal=postgres-password=$(openssl rand -base64 24) \
  --from-literal=neo4j-password=$(openssl rand -base64 24) \
  --namespace=Meatapivot

# Apply all manifests
kubectl apply -f deploy/k8s/ -R

# Check status
kubectl get pods -n Meatapivot
```

### Recommended k8s Resources

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---------|------------|-----------|----------------|--------------|
| backend | 500m | 2000m | 1Gi | 4Gi |
| frontend | 100m | 500m | 256Mi | 512Mi |
| postgres | 1000m | 4000m | 2Gi | 8Gi |
| neo4j | 1000m | 4000m | 2Gi | 8Gi |
| redis | 100m | 500m | 256Mi | 512Mi |
| minio | 500m | 2000m | 1Gi | 4Gi |

---

## Monitoring & Alerting

### Pre-configured Dashboards

Grafana comes with three pre-configured dashboards in
`cicd/grafana/dashboards/`:

1. **API Performance** — Request rate, latency P50/P95/P99, error rate
2. **Database Performance** — PostgreSQL/Neo4j/Redis metrics
3. **Ontology Compilation** — Compile duration, errors, rollback events

### Prometheus Alerts

Edit `cicd/prometheus/alerts.yml`:

```yaml
groups:
  - name: meatapivot
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        annotations:
          summary: "5xx error rate above 10%"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        annotations:
          summary: "P95 latency above 1s"

      - alert: DatabaseConnectionsHigh
        expr: pg_stat_activity_count > 80
        for: 5m
        annotations:
          summary: "PostgreSQL connections above 80"
```

### Key Metrics to Monitor

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| API P50 latency | < 100ms | > 200ms | > 500ms |
| API P95 latency | < 500ms | > 1000ms | > 2000ms |
| 5xx error rate | < 0.1% | > 1% | > 5% |
| DB connections | < 50 | > 80 | > 95 |
| Redis hit rate | > 95% | > 80% | < 70% |
| Disk usage | < 70% | > 85% | > 95% |
| CPU usage | < 60% | > 80% | > 95% |
| Memory usage | < 70% | > 85% | > 95% |

---

## Backup & Recovery

### Backup Strategy

- **PostgreSQL**: Daily full backup + WAL archiving (point-in-time recovery)
- **Neo4j**: Daily full backup
- **MinIO**: Daily mirror to off-site storage
- **Redis**: AOF persistence enabled

### Recovery Procedures

#### PostgreSQL Restore

```bash
# Stop backend
docker-compose stop backend worker

# Restore database
gunzip -c backup.sql.gz | docker-compose exec -T postgres psql -U knowledge knowledge_db

# Restart backend
docker-compose start backend worker
```

#### Neo4j Restore

```bash
docker-compose stop neo4j
docker-compose run --rm neo4j neo4j-admin load \
  --from=/var/lib/neo4j/backup/neo4j_backup.dump \
  --database=neo4j --force
docker-compose start neo4j
```

---

## Troubleshooting

### Backend won't start

```bash
# Check logs
docker-compose logs backend

# Common issues:
# 1. Database connection failed
docker-compose exec backend env | grep DATABASE_URL
docker-compose exec postgres pg_isready -U knowledge

# 2. Migration needed
docker-compose exec backend alembic current
docker-compose exec backend alembic upgrade head
```

### High memory usage

```bash
# Check memory per container
docker stats

# Common culprits:
# - Neo4j: increase HEAP_SIZE in docker-compose
# - Backend: check for memory leaks in logs
# - Redis: check maxmemory config
```

### Slow API responses

```bash
# Check slow queries
docker-compose exec postgres psql -U knowledge -d knowledge_db \
  -c "SELECT pid, query, state, query_start FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start;"

# Check Redis cache hit rate
docker-compose exec redis redis-cli INFO stats | grep keyspace
```

### MinIO issues

```bash
# Check MinIO health
curl http://localhost:9000/minio/health/live

# List buckets
mc alias set local http://localhost:9000 minioadmin minioadmin123
mc ls local/
```

---

## Support

- **Documentation**: https://docs.Meatapivot.io
- **Issues**: https://github.com/yourorg/Meatapivot/issues
- **Discord**: https://discord.gg/Meatapivot
- **Email**: support@Meatapivot.io

---

**Last updated**: 2026-06-11
**Version**: 2.2.0
