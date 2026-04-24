#!/bin/bash

###############################################################################
# AI 网关 (ai-gateway) Docker 部署脚本
# 功能: 停止现有容器、拉取新镜像、启动新容器
###############################################################################

set -e  # 遇到错误立即退出

# ==================== 配置区域 ====================

# 根据 PROFILES_ACTIVE 确定镜像命名空间
if [[ "${PROFILES_ACTIVE}" == "dev" ]]; then
    NAMESPACE="leczcore_dev"
else
    NAMESPACE="leczcore_prod"
fi

# Docker 镜像配置
IMAGE_NAME="crpi-301jbh81iyvo39lb.cn-beijing.personal.cr.aliyuncs.com/${NAMESPACE}/ai-gateway"  # 镜像名称
IMAGE_TAG="latest"                        # 镜像标签 (流水线通常注入真实的tag，可通过环境变量覆盖)
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

# 容器配置
CONTAINER_NAME="ai-gateway" # 容器名称
HOST_PORT=8000
CONTAINER_PORT=8000         # 容器内启动暴露的端口 (对应 Dockerfile 里的 EXPOSE 8000)

# 环境变量配置
ENV_VARS=(
    "-e ENVIRONMENT=${PROFILES_ACTIVE}"
    "-e TZ=Asia/Shanghai"
)

# 可选: 数据卷挂载 (可根据实际需求增加大模型缓存等映射)
VOLUMES=(
    "-v /data/app/ai-platform/ai-gateway/logs:/app/logs"
)

# 网络配置
NETWORK="--network bridge"

# ==================== 颜色输出 ====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ==================== 日志函数 ====================
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# ==================== 主要功能函数 ====================

# 检查 Docker 是否运行
check_docker() {
    log_info "检查 Docker 服务状态..."
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker 未运行或无权限访问"
        exit 1
    fi
    log_info "Docker 服务正常"
}

# 停止并删除现有容器
stop_container() {
    log_info "检查容器 ${CONTAINER_NAME} 是否存在..."
    
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "发现容器 ${CONTAINER_NAME}，准备停止..."
        
        # 停止容器
        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            docker stop ${CONTAINER_NAME}
            log_info "容器已停止"
        else
            log_warn "容器已经是停止状态"
        fi
        
        # 删除容器
        docker rm ${CONTAINER_NAME}
        log_info "容器已删除"
    else
        log_warn "容器 ${CONTAINER_NAME} 不存在，跳过停止步骤"
    fi
}

# 清理旧镜像（可选）
cleanup_old_images() {
    log_info "清理悬空镜像..."
    docker image prune -f > /dev/null 2>&1 || true
    log_info "悬空镜像清理完成"
}

# 拉取新镜像
pull_image() {
    log_info "开始尝试拉取镜像: ${FULL_IMAGE}"
    
    # 尝试登录 (如果凭证在环境变量中存在)
    if [ ! -z "$ALIYUN_PASSWORD" ] && [ ! -z "$ALIYUN_USER" ]; then
        log_info "正在使用凭证登录镜像仓库..."
        echo "${ALIYUN_PASSWORD}" | docker login --username "${ALIYUN_USER}" --password-stdin crpi-301jbh81iyvo39lb.cn-beijing.personal.cr.aliyuncs.com || true
    fi

    if docker pull ${FULL_IMAGE}; then
        log_info "镜像拉取成功"
    else
        log_warn "镜像拉取失败或走本地构建，不再强行阻断"
    fi
}

# 启动新容器
start_container() {
    log_info "启动新容器: ${CONTAINER_NAME}"
    
    # 构建 docker run 命令
    DOCKER_RUN_CMD="docker run -d \
        --name ${CONTAINER_NAME} \
        --restart=always \
        -p ${HOST_PORT}:${CONTAINER_PORT} \
        ${NETWORK} \
        ${ENV_VARS[@]} \
        ${VOLUMES[@]} \
        ${FULL_IMAGE}"
    
    # 执行启动命令
    if eval ${DOCKER_RUN_CMD}; then
        log_info "容器启动成功"
    else
        log_error "容器启动失败"
        exit 1
    fi
}

# 健康检查
health_check() {
    log_info "等待应用启动..."
    sleep 3
    
    log_info "检查容器运行状态..."
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "容器运行正常"
        
        # 显示容器日志（最后 20 行）
        log_info "容器日志（最后 20 行）:"
        echo "----------------------------------------"
        docker logs --tail 20 ${CONTAINER_NAME} || true
        echo "----------------------------------------"
        
        return 0
    else
        log_error "容器未正常运行"
        
        # 显示容器日志用于排查问题
        log_error "容器崩溃日志:"
        docker logs ${CONTAINER_NAME} || true
        
        exit 1
    fi
}

# 显示容器信息
show_container_info() {
    log_info "容器信息:"
    echo "----------------------------------------"
    docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo "----------------------------------------"
}

# ==================== 主流程 ====================
main() {
    log_info "========== 开始部署 AI网关 (AI-Gateway) =========="
    log_info "当前运行环境 (PROFILE): ${PROFILES_ACTIVE:-prod}"
    log_info "目标镜像: ${FULL_IMAGE}"
    log_info "对外端口映射: ${HOST_PORT}:${CONTAINER_PORT}"
    echo ""
    
    # 1. 检查 Docker
    check_docker
    
    # 2. 停止并删除现有容器
    stop_container
    
    # 3. 拉取新镜像
    pull_image
    
    # 4. 启动新容器
    start_container
    
    # 5. 清理旧镜像（可选，放在启动完成后避免误删基础层）
    cleanup_old_images
    
    # 6. 健康检查
    health_check
    
    # 7. 显示容器信息
    show_container_info
    
    log_info "========== 部署完成 =========="
}

# 执行主流程
main
