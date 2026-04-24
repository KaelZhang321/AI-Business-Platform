#!/bin/bash
set -e

# This script is executed on the REMOTE server.
# Environment variables like ALIYUN_REGISTRY, FULL_IMAGE_NAME, etc. are expected to be exported by the SSH session.

echo "=== Remote Deployment for $FULL_IMAGE_NAME ==="

# 1. Login to Aliyun Registry
echo "Logging into Aliyun Registry on remote..."
echo "$ALIYUN_PASSWORD" | docker login --username "$ALIYUN_USER" --password-stdin "$ALIYUN_REGISTRY"

# 2. Pull the latest image
echo "Pulling latest image: $FULL_IMAGE_NAME"
docker pull "$FULL_IMAGE_NAME"

# 3. Stop and remove existing container
# Assuming container name is IMAGE_NAME
echo "Stopping container: $IMAGE_NAME"
if [ "$(docker ps -aq -f name=^/${IMAGE_NAME}$)" ]; then
    docker stop "$IMAGE_NAME"
    docker rm "$IMAGE_NAME"
fi

# 4. Run new container
# Make sure to adjust ports/volumes as needed
echo "Running new container: $IMAGE_NAME"
docker run -d \
  --name "$IMAGE_NAME" \
  --restart unless-stopped \
  -p 80:80 \
  "$FULL_IMAGE_NAME"

# 5. Clean up old images (optional)
echo "Cleaning up dangling images..."
docker image prune -f

echo "=== Remote Deployment Successful ==="
