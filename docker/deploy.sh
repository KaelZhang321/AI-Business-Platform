#!/bin/bash
# ═══════════════════════════════════════════════════════════
# AI业务中台 — 一键部署脚本
# 用法: cd docker && bash deploy.sh [infra|gateway|business|frontend|all]
# ═══════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_DIR="$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 确保 Docker 网络存在 ────────────────────────────────
ensure_network() {
    if ! docker network inspect ai-platform-net &>/dev/null; then
        log_info "创建 Docker 网络: ai-platform-net"
        docker network create ai-platform-net
    fi
}

# ── 1. 基础设施服务 ─────────────────────────────────────
deploy_infra() {
    log_info "启动基础设施服务..."
    cd "$COMPOSE_DIR"
    docker compose up -d
    log_info "等待服务健康检查..."
    sleep 10
    docker compose ps
}

# ── 2. AI网关 ───────────────────────────────────────────
deploy_gateway() {
    log_info "构建并启动 AI 网关..."
    cd "$COMPOSE_DIR"
    docker compose -f docker-compose.ai-gateway.yml build --no-cache
    docker compose -f docker-compose.ai-gateway.yml up -d
    log_info "AI 网关已启动，等待健康检查..."
    sleep 5
    docker logs ai-platform-ai-gateway --tail 20
}

# ── 3. 业务编排层 ───────────────────────────────────────
deploy_business() {
    log_info "构建并启动业务编排服务..."
    cd "$COMPOSE_DIR"
    docker compose -f docker-compose.business-server.yml build --no-cache
    docker compose -f docker-compose.business-server.yml up -d
    log_info "业务编排服务已启动，等待健康检查..."
    sleep 10
    docker logs ai-platform-business-server --tail 20
}

# ── 4. 前端构建 ─────────────────────────────────────────
deploy_frontend() {
    log_info "构建前端项目..."
    cd "$PROJECT_DIR/frontend"

    # 安装依赖
    if [ ! -d "node_modules" ]; then
        log_info "安装前端依赖..."
        npm install
    fi

    # 构建
    log_info "执行 npm run build..."
    npm run build

    # 复制到 Docker volume
    VOLUME_PATH=$(docker volume inspect docker_frontend_dist --format '{{.Mountpoint}}' 2>/dev/null || \
                  docker volume inspect ai-platform-net_frontend_dist --format '{{.Mountpoint}}' 2>/dev/null || \
                  echo "")

    if [ -z "$VOLUME_PATH" ]; then
        log_info "创建前端 volume 并复制文件..."
        # 通过临时容器复制文件到 volume
        docker run --rm \
            -v docker_frontend_dist:/dist \
            -v "$PROJECT_DIR/frontend/dist":/src \
            alpine sh -c "rm -rf /dist/* && cp -r /src/* /dist/"
    else
        log_info "复制前端构建产物到 volume: $VOLUME_PATH"
        sudo rm -rf "$VOLUME_PATH"/*
        sudo cp -r "$PROJECT_DIR/frontend/dist"/* "$VOLUME_PATH"/
    fi

    # 重启 Nginx
    log_info "重启 Nginx..."
    cd "$COMPOSE_DIR"
    docker compose restart nginx
    log_info "前端部署完成"
}

# ── 5. 全量部署 ─────────────────────────────────────────
deploy_all() {
    ensure_network
    deploy_infra
    deploy_gateway
    deploy_business
    deploy_frontend
    log_info "==============================="
    log_info "  全部服务部署完成!"
    log_info "  访问: http://$(hostname -I | awk '{print $1}'):80"
    log_info "==============================="
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep ai-platform
}

# ── 主入口 ──────────────────────────────────────────────
case "${1:-all}" in
    infra)    ensure_network && deploy_infra ;;
    gateway)  ensure_network && deploy_gateway ;;
    business) ensure_network && deploy_business ;;
    frontend) deploy_frontend ;;
    all)      deploy_all ;;
    *)
        echo "用法: bash deploy.sh [infra|gateway|business|frontend|all]"
        exit 1
        ;;
esac
