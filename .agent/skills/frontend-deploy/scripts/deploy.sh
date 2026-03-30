#!/bin/bash
set -e

# ===== 模块名参数 =====
# 用法: deploy.sh [模块名]
# 默认模块名: frontend
MODULE_NAME="${1:-frontend}"
MODULE_PREFIX="MODULE_$(echo "$MODULE_NAME" | tr '[:lower:]' '[:upper:]')_"

echo "=== Deploying module: $MODULE_NAME ==="

# ===== 加载统一的 .env =====
CONFIG_FILE=".env"
if [ -f "$CONFIG_FILE" ]; then
  echo "Loading configuration from $CONFIG_FILE"
  # 逐行读取，安全处理特殊字符 ($, &, ! 等)
  while IFS= read -r line || [[ -n "$line" ]]; do
    # 跳过空行和注释
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    # 提取 key（第一个 = 前的部分）和 value（第一个 = 后的所有内容）
    key="${line%%=*}"
    value="${line#*=}"
    # 去掉 key 的首尾空格
    key="${key// /}"
    [[ -z "$key" ]] && continue
    export "$key=$value"
  done < "$CONFIG_FILE"
else
  echo "Error: Configuration file '$CONFIG_FILE' not found."
  exit 1
fi

# ===== 提取模块专属变量，覆盖公共变量 =====
# 例如 MODULE_FRONTEND_IMAGE_NAME=crm-web → IMAGE_NAME=crm-web
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  key="${key// /}"
  key_upper="$(echo "$key" | tr '[:lower:]' '[:upper:]')"
  if [[ "$key_upper" == ${MODULE_PREFIX}* ]]; then
    base_key="${key_upper#$MODULE_PREFIX}"
    export "$base_key=$value"
    echo "  [module] $base_key=$value"
  fi
done < "$CONFIG_FILE"

# ===== 环境变量检查 =====
check_env() {
  local var_name="$1"
  if [ -z "${!var_name}" ]; then
    echo "Error: Environment variable '$var_name' is not set."
    exit 1
  fi
}

check_env "ALIYUN_REGISTRY"
check_env "ALIYUN_NAMESPACE"
check_env "ALIYUN_USER"
check_env "ALIYUN_PASSWORD"
check_env "IMAGE_NAME"
check_env "REMOTE_USER"
check_env "REMOTE_HOST"
check_env "REMOTE_DIR"

# Defaults
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Auto-detect build command if not set
if [ -z "$BUILD_CMD" ]; then
  if [ -f "yarn.lock" ]; then
     echo "Detected yarn project. Setting build command to 'yarn build'."
     BUILD_CMD="yarn build"
  elif [ -f "pnpm-lock.yaml" ]; then
     echo "Detected pnpm project. Setting build command to 'pnpm build'."
     BUILD_CMD="pnpm build"
  elif [ -f "package.json" ]; then
    echo "Detected Node.js project. Setting build command to 'npm run build'."
    BUILD_CMD="npm run build"
  else
    echo "Warning: No build command specified and no known project file detected."
    BUILD_CMD="true"
  fi
fi
REMOTE_SCRIPT="${REMOTE_SCRIPT:-./skills/frontend-deploy/scripts/remote_deploy_template.sh}"
DOCKERFILE="${DOCKERFILE:-./Dockerfile}"
BUILD_CONTEXT="${BUILD_CONTEXT:-.}"

FULL_IMAGE_NAME="$ALIYUN_REGISTRY/$ALIYUN_NAMESPACE/$IMAGE_NAME:$IMAGE_TAG"

echo "=== Starting Deployment for $IMAGE_NAME:$IMAGE_TAG ==="

# --- 1. Git Automation ---
echo "--- 1. Git Automation ---"
if [ "$GIT_COMMIT_ENABLED" != "false" ]; then
  if [ -n "$(git status --porcelain)" ]; then
    echo "Changes detected. Committing and pushing..."
    git add .
    
    # Generate a summary of changed files for the commit message
    CHANGED_FILES=$(git diff --name-only --cached | head -n 5 | tr '\n' ',' | sed 's/,$//' | sed 's/,/, /g')
    TOTAL_FILES=$(git diff --name-only --cached | wc -l | tr -d ' ')
    
    if [ "$TOTAL_FILES" -gt 5 ]; then
        COMMIT_MSG="chore: auto-deploy - updated $CHANGED_FILES and $(($TOTAL_FILES - 5)) more files ($(date +'%Y-%m-%d %H:%M:%S'))"
    else
        COMMIT_MSG="chore: auto-deploy - updated $CHANGED_FILES ($(date +'%Y-%m-%d %H:%M:%S'))"
    fi
    
    git commit -m "$COMMIT_MSG"
    git push
  else
    echo "No changes to commit."
  fi
else
  echo "Git commit disabled (GIT_COMMIT_ENABLED=false). Skipping."
fi

# --- 2. Build ---
echo "--- 2. Building Application ---"
eval "$BUILD_CMD"

# --- 3. Docker Build & Push ---
echo "--- 3. Docker Build & Push ---"
echo "Logging into Aliyun Registry..."
echo "$ALIYUN_PASSWORD" | docker login --username "$ALIYUN_USER" --password-stdin "$ALIYUN_REGISTRY"

echo "Building Docker Image (forcing linux/amd64 for cross-platform compatibility)..."
echo "Dockerfile: $DOCKERFILE"
echo "Context: $BUILD_CONTEXT"
if [ -n "$BUILD_ENV" ]; then
    echo "Using BUILD_ENV: $BUILD_ENV"
    docker build --platform linux/amd64 --build-arg BUILD_ENV="$BUILD_ENV" -f "$DOCKERFILE" -t "$FULL_IMAGE_NAME" "$BUILD_CONTEXT"
else
    docker build --platform linux/amd64 -f "$DOCKERFILE" -t "$FULL_IMAGE_NAME" "$BUILD_CONTEXT"
fi

echo "Pushing Docker Image..."
docker push "$FULL_IMAGE_NAME"

# --- 4. Remote Execution ---
echo "--- 4. Remote Deployment ---"

execute_remote() {
    local script_path="$1"
    
    local env_vars="export ALIYUN_REGISTRY='$ALIYUN_REGISTRY'; export ALIYUN_NAMESPACE='$ALIYUN_NAMESPACE'; export ALIYUN_USER='$ALIYUN_USER'; export ALIYUN_PASSWORD='$ALIYUN_PASSWORD'; export IMAGE_NAME='$IMAGE_NAME'; export IMAGE_TAG='$IMAGE_TAG'; export FULL_IMAGE_NAME='$FULL_IMAGE_NAME'; export REMOTE_DIR='$REMOTE_DIR';"

    if [ -n "$REMOTE_PASSWORD" ]; then
        if ! command -v sshpass &>/dev/null; then
            echo "Error: REMOTE_PASSWORD is set but 'sshpass' is not installed."
            echo "Please install sshpass (e.g., brew install sshpass) or use SSH keys."
            exit 1
        fi
        echo "Using password authentication (sshpass)..."
        sshpass -p "$REMOTE_PASSWORD" ssh -o StrictHostKeyChecking=no "$REMOTE_USER@$REMOTE_HOST" "$env_vars bash -s" < "$script_path"
    else
        echo "Using key-based authentication..."
        ssh "$REMOTE_USER@$REMOTE_HOST" "$env_vars bash -s" < "$script_path"
    fi
}

execute_remote "$REMOTE_SCRIPT"

echo "=== Deployment Completed Successfully ==="
