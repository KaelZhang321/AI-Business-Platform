#!/bin/bash

###############################################################################
# Spring Boot Docker 部署脚本
# 功能: 停止现有容器、拉取新镜像、启动新容器
###############################################################################

set -e  # 遇到错误立即退出

# ==================== 配置区域 ====================
# 请根据实际情况修改以下配置


# 根据 PROFILES_ACTIVE 确定镜像命名空间
if [[ "${PROFILES_ACTIVE}" == "dev" ]]; then
    NAMESPACE="leczcore_dev"
else
    NAMESPACE="leczcore_prod"
fi

# Docker 镜像配置
IMAGE_NAME="crpi-301jbh81iyvo39lb.cn-beijing.personal.cr.aliyuncs.com/${NAMESPACE}/business-server"  # 镜像名称
IMAGE_TAG="1.0.0"                         # 镜像标签
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

# 容器配置
CONTAINER_NAME="business-server" # 容器名称
HOST_PORT=8080 # 宿主机端口
CONTAINER_PORT=8080 # 容器端口

if [[ "${PROFILES_ACTIVE}" == "dev" ]]; then
    HOST_PORT=8080
else
    HOST_PORT=8081
fi
# 可选: 环境变量配置
ENV_VARS=(
    "-e SPRING_PROFILES_ACTIVE=${PROFILES_ACTIVE}"
    "-e TZ=Asia/Shanghai"
)

# 可选: 数据卷挂载
VOLUMES=(
    "-v /data/app/ai-platform/business-server/logs:/data/app/ai-platform/business-server/logs"
)

# 可选: 网络配置
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
    log_info "登录镜像仓库..."
    echo "${ALIYUN_PASSWORD}" | docker login --username "${ALIYUN_USER}" --password-stdin "${ALIYUN_REGISTRY}" || true

    log_info "开始拉取镜像: ${FULL_IMAGE}"
    
    if docker pull ${FULL_IMAGE}; then
        log_info "镜像拉取成功"
    else
        log_error "镜像拉取失败"
        exit 1
    fi
}

# 启动新容器
start_container() {
    log_info "启动新容器: ${CONTAINER_NAME}"
    
    # 构建 docker run 命令
    DOCKER_RUN_CMD="docker run -d \
        --name ${CONTAINER_NAME} \
        --restart=unless-stopped \
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
    sleep 5
    
    log_info "检查容器运行状态..."
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "容器运行正常"
        
        # 显示容器日志（最后 20 行）
        log_info "容器日志（最后 20 行）:"
        echo "----------------------------------------"
        docker logs --tail 20 ${CONTAINER_NAME}
        echo "----------------------------------------"
        
        return 0
    else
        log_error "容器未正常运行"
        
        # 显示容器日志用于排查问题
        log_error "容器日志:"
        docker logs ${CONTAINER_NAME}
        
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
    log_info "========== 开始部署 =========="
    log_info "镜像: ${FULL_IMAGE}"
    log_info "容器: ${CONTAINER_NAME}"
    log_info "端口: ${HOST_PORT}:${CONTAINER_PORT}"
    echo ""
    
    # 1. 检查 Docker
    check_docker
    
    # 2. 停止并删除现有容器
    stop_container
    
    # 3. 拉取新镜像
    pull_image
    
    # 4. 清理旧镜像（可选）
    cleanup_old_images
    
    # 5. 启动新容器
    start_container
    
    # 6. 健康检查
    health_check
    
    # 7. 显示容器信息
    show_container_info
    
    log_info "========== 部署完成 =========="
}

# 执行主流程
main
