#!/bin/bash

set -e

echo "🚀 Starting Meatapivot Development Environment..."

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Create necessary directories
echo -e "${YELLOW}📁 Creating data directories...${NC}"
mkdir -p data/{postgres,neo4j,rabbitmq,minio}

# Copy environment file if not exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}📝 Creating .env file from .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✅ .env file created. Please update the values as needed.${NC}"
fi

# Start all services
echo -e "${YELLOW}🐳 Starting Docker Compose services...${NC}"
docker-compose up -d

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
sleep 30

# Check service health
echo -e "${YELLOW}🔍 Checking service health...${NC}"

# Check PostgreSQL
if docker-compose exec -T postgres pg_isready -U knowledge &> /dev/null; then
    echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
else
    echo -e "${YELLOW}⚠️  PostgreSQL may still be starting...${NC}"
fi

# Check Neo4j
if curl -s http://localhost:7474 &> /dev/null; then
    echo -e "${GREEN}✅ Neo4j is ready${NC}"
else
    echo -e "${YELLOW}⚠️  Neo4j may still be starting...${NC}"
fi

# Check RabbitMQ
if curl -s http://localhost:15672 &> /dev/null; then
    echo -e "${GREEN}✅ RabbitMQ Management is ready${NC}"
else
    echo -e "${YELLOW}⚠️  RabbitMQ may still be starting...${NC}"
fi

# Check MinIO
if curl -s http://localhost:9001 &> /dev/null; then
    echo -e "${GREEN}✅ MinIO Console is ready${NC}"
else
    echo -e "${YELLOW}⚠️  MinIO may still be starting...${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 Development environment started!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Service URLs:${NC}"
echo "  - Frontend:        http://localhost:5173"
echo "  - Backend API:     http://localhost:8000"
echo "  - API Docs:        http://localhost:8000/docs"
echo "  - PostgreSQL:      localhost:5432"
echo "  - Neo4j Browser:   http://localhost:7474"
echo "  - RabbitMQ Mgmt:   http://localhost:15672"
echo "  - MinIO Console:   http://localhost:9001"
echo "  - Keycloak:        http://localhost:8080"
echo ""
echo -e "${YELLOW}Default Credentials:${NC}"
echo "  - PostgreSQL:    knowledge / kpassword"
echo "  - Neo4j:         neo4j / neo4jpassword"
echo "  - RabbitMQ:      user / rabbitmq"
echo "  - MinIO:         minioadmin / minioadmin123"
echo "  - Keycloak:      admin / admin123"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Install backend dependencies: cd backend && pip install -r requirements.txt"
echo "  2. Install frontend dependencies: cd frontend && npm install"
echo "  3. Start backend: cd backend && uvicorn app.main:app --reload"
echo "  4. Start frontend: cd frontend && npm run dev"
echo ""