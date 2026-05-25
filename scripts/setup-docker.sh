#!/usr/bin/env bash
# Meatapivot Docker 环境搭建脚本
# 适用于 macOS + Colima（轻量级 Docker 替代）

set -e

echo "=== Meatapivot Docker 环境搭建 ==="
echo ""

# 检查 Homebrew
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew 未安装"
    echo "请先安装 Homebrew:"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
fi

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "📦 安装 Docker CLI..."
    brew install docker docker-compose
fi

# 检查 Colima
if ! command -v colima &> /dev/null; then
    echo "📦 安装 Colima..."
    brew install colima
fi

echo "✅ 依赖已安装"
echo ""

# 启动 Colima（如果未运行）
if ! colima status 2>/dev/null | grep -q "Running"; then
    echo "🚀 启动 Colima VM（内存 8GB，CPU 4核）..."
    colima start --cpu 4 --memory 8 --disk 60 --arch aarch64
else
    echo "✅ Colima 已在运行"
fi

echo ""
echo "=== Docker 环境就绪 ==="
docker --version
docker-compose --version
echo ""

# 进入项目目录
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "=== 启动 Meatapivot 服务 ==="
echo ""
echo "请选择启动模式："
echo "  1) 轻量模式（推荐开发）- PostgreSQL + Neo4j + Redis + Backend + Frontend"
echo "  2) 完整模式 - 20+ 服务（含 Milvus, Keycloak, Grafana 等）"
echo ""

read -p "请选择 [1/2]: " choice

if [ "$choice" == "2" ]; then
    COMPOSE_FILE="docker-compose.deploy.yml"
    echo "📦 使用完整部署模式..."
else
    COMPOSE_FILE="docker-compose.light.yml"
    echo "📦 使用轻量开发模式..."
fi

# 检查 .env
if [ ! -f ".env" ]; then
    echo "⚠️  .env 文件不存在，从 .env.deploy 复制..."
    cp .env.deploy .env
    echo "⚠️  请编辑 .env 文件修改默认密码！"
fi

# 启动服务
echo ""
echo "🚀 启动服务..."
docker-compose -f "$COMPOSE_FILE" --env-file .env up -d --build

echo ""
echo "=== 服务启动完成 ==="
echo ""
echo "访问地址："
echo "  Frontend:    http://localhost:3000"
echo "  Backend API: http://localhost:8000"
echo "  API Docs:    http://localhost:8000/docs"
echo "  Neo4j:       http://localhost:7474"
echo ""

# 等待 PostgreSQL 就绪
echo "⏳ 等待 PostgreSQL 就绪..."
sleep 5

# 运行 Alembic 迁移
echo ""
echo "🔄 运行数据库迁移..."
cd backend
if [ -f "alembic.ini" ]; then
    # 使用 docker exec 在容器内运行 alembic
    docker exec meatapivot-backend alembic upgrade head 2>/dev/null || \
        echo "⚠️  迁移失败，请手动运行: docker exec -it meatapivot-backend alembic upgrade head"
else
    echo "⚠️  alembic.ini 不存在，跳过迁移"
fi

echo ""
echo "✅ 环境搭建完成！"
echo ""
echo "常用命令："
echo "  查看日志:   docker-compose -f $COMPOSE_FILE logs -f backend"
echo "  停止服务:   docker-compose -f $COMPOSE_FILE down"
echo "  重启服务:   docker-compose -f $COMPOSE_FILE restart"
echo "  进入容器:   docker exec -it meatapivot-backend bash"
echo ""
