#!/bin/bash
set -e

# This script is executed on the REMOTE server.
# The deploy script passes FULL_IMAGE_NAME. Do not recalculate it here,
# otherwise test deployments may accidentally pull the production image.
IMAGE_TAG="${IMAGE_TAG:-1.0.0}"
IMAGE_NAME="${IMAGE_NAME:-ai-web}"
ALIYUN_REGISTRY="${ALIYUN_REGISTRY:-crpi-301jbh81iyvo39lb.cn-beijing.personal.cr.aliyuncs.com}"

if [ -z "$FULL_IMAGE_NAME" ]; then
    if [ -z "$ALIYUN_NAMESPACE" ]; then
        if [[ "${BUILD_ENV}" == "test" || "${PROFILES_ACTIVE}" == "dev" ]]; then
            ALIYUN_NAMESPACE="leczcore_dev"
        else
            ALIYUN_NAMESPACE="leczcore_prod"
        fi
    fi

    if [[ "$IMAGE_NAME" == */* ]]; then
        FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"
    else
        FULL_IMAGE_NAME="${ALIYUN_REGISTRY}/${ALIYUN_NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}"
    fi
fi

echo "=== Remote Deployment for $FULL_IMAGE_NAME ==="

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
