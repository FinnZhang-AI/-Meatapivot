#!/bin/bash

set -e

echo "🚀 Starting Meatapivot - Local Development Mode"
echo "⚠️  Running without Docker (degraded mode - services will use fallback)"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Create .env for local dev
cat > .env << 'EOF'
# Application Settings
APP_NAME=Meatapivot
DEBUG=true
HOST=0.0.0.0
PORT=8000
API_PREFIX=/api/v1

# Database - Using SQLite for local dev (fallback mode)
DATABASE_URL=sqlite+aiosqlite:///./knowledge_local.db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=knowledge
POSTGRES_PASSWORD=kpassword
POSTGRES_DB=knowledge_db

# Neo4j - Fallback mode
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4jpassword

# RabbitMQ - Fallback mode
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=user
RABBITMQ_PASSWORD=rabbitmq
RABBITMQ_URL=amqp://user:rabbitmq@localhost:5672/

# MinIO - Fallback mode
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET=documents
MINIO_SECURE=false

# Keycloak
KEYCLOAK_SERVER_URL=http://localhost:8080
KEYCLOAK_REALM=knowledge-platform
KEYCLOAK_CLIENT_ID=knowledge-client

# Security
SECRET_KEY=local-dev-secret-key
JWT_SECRET_KEY=local-jwt-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# File Upload
MAX_UPLOAD_SIZE=104857600
ALLOWED_EXTENSIONS=pdf,docx,txt,md,csv,xlsx,xls,pptx,jpg,png

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
EOF

echo -e "${GREEN}✅ Environment file created${NC}"

# Install backend dependencies
echo -e "${YELLOW}📦 Installing backend dependencies...${NC}"
cd backend
pip install -r requirements.txt -q
cd ..

# Install frontend dependencies
echo -e "${YELLOW}📦 Installing frontend dependencies...${NC}"
cd frontend
npm install --silent
cd ..

# Create data directory
mkdir -p data

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 Starting services in degraded mode${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Note: External services (PostgreSQL, Neo4j, RabbitMQ, MinIO) are not available.${NC}"
echo -e "${YELLOW}Application will run with limited functionality.${NC}"
echo ""
echo -e "${YELLOW}Service URLs:${NC}"
echo "  - Frontend:    http://localhost:5173"
echo "  - Backend API: http://localhost:8000"
echo "  - API Docs:    http://localhost:8000/docs"
echo ""

# Start backend in background
echo -e "${YELLOW}🔧 Starting backend server...${NC}"
cd backend
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

sleep 5

# Start frontend in background
echo -e "${YELLOW}🎨 Starting frontend dev server...${NC}"
cd frontend
nohup npm run dev -- --host 0.0.0.0 --port 5173 > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

sleep 5

echo ""
echo -e "${GREEN}✅ Services started!${NC}"
echo "  - Backend PID:  $BACKEND_PID"
echo "  - Frontend PID: $FRONTEND_PID"
echo ""
echo -e "${YELLOW}To stop services: kill $BACKEND_PID $FRONTEND_PID${NC}"
echo ""

# Health check
echo -e "${YELLOW}🔍 Performing health check...${NC}"
sleep 3

if curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✅ Backend is responding${NC}"
    curl -s http://localhost:8000/health | head -c 200
    echo ""
else
    echo -e "${RED}❌ Backend health check failed${NC}"
fi

if curl -s http://localhost:5173 > /dev/null; then
    echo -e "${GREEN}✅ Frontend is responding${NC}"
else
    echo -e "${RED}❌ Frontend health check failed${NC}"
fi

echo ""
echo -e "${GREEN}🎉 End-to-end test environment ready!${NC}"