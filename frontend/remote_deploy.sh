#!/bin/bash
set -e

# This script is executed on the REMOTE server.
# Environment variables like ALIYUN_REGISTRY, FULL_IMAGE_NAME, etc. are passed by the deploy script.

ALIYUN_REGISTRY=crpi-301jbh81iyvo39lb-vpc.cn-beijing.personal.cr.aliyuncs.com
IMAGE_NAME=ai-web
IMAGE_TAG=1.0.0

echo "=== Remote Deployment for $FULL_IMAGE_NAME ==="

# 2. Pull the latest image
echo "Pulling latest image: $FULL_IMAGE_NAME"
# Use IMAGE_TAG or default to 'latest'
IMAGE_TAG=${IMAGE_TAG:-latest}

# 根据 PROFILES_ACTIVE 确定镜像命名空间
if [[ "${BUILD_ENV}" == "test" ]]; then
    ALIYUN_NAMESPACE="leczcore_dev"
elif [[ "${BUILD_ENV}" == "prod" ]]; then
    ALIYUN_NAMESPACE="leczcore_prod"
else 
    ALIYUN_NAMESPACE="leczcore_dev"
fi

FULL_IMAGE_NAME="${ALIYUN_REGISTRY}/${ALIYUN_NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}"

docker pull "$FULL_IMAGE_NAME"

# 3. Stop and remove existing container
# Assuming container name is IMAGE_NAME (ai-web)
IMAGE_NAME_CONTAINER="ai-web"
echo "Stopping container: $IMAGE_NAME_CONTAINER"
if [ "$(docker ps -aq -f name=^/${IMAGE_NAME_CONTAINER}$)" ]; then
    docker stop "$IMAGE_NAME_CONTAINER"
    docker rm "$IMAGE_NAME_CONTAINER"
fi

# 4. Run new container
# Mapping 8900 to 80 (Nginx default)
echo "Running new container: $IMAGE_NAME_CONTAINER on port 8079"
docker run -d \
  --name "$IMAGE_NAME_CONTAINER" \
  --restart unless-stopped \
  -p 8079:80 \
  "$FULL_IMAGE_NAME"

# 5. Clean up old images (optional)
echo "Cleaning up dangling images..."
docker image prune -f

echo "=== Remote Deployment Successful for $IMAGE_NAME_CONTAINER ==="
