---
name: 前端自动部署 (Frontend Auto-Deployment)
description: 自动化代码提交、构建、推送Docker镜像到阿里云镜像仓库，并执行远程服务器部署脚本。
---

# 前端自动部署 (Frontend Auto-Deployment)

这个 Skill 旨在自动化前端服务的部署流程，主要包含以下步骤：
1.  **Git 自动化**: 自动提交并推送本地代码变更。
2.  **构建 (Build)**: 执行用户自定义的构建命令。
3.  **Docker**: 构建 Docker 镜像（自动指定 `linux/amd64` 架构以兼容 Linux 服务器），登录阿里云容器镜像服务 (ACR)，打标签并推送镜像。
4.  **远程部署**: 通过 SSH 连接到远程服务器，拉取最新镜像并重启服务。

## 前置条件 (Prerequisites)

1.  **Docker**: 本地必须安装并运行 Docker。
2.  **阿里云账号**: 需要阿里云容器镜像服务 (ACR) 的访问权限（命名空间、账号、密码）。
3.  **SSH 访问**: 需要配置好到远程服务器的 SSH 密钥认证（免密登录），或者安装 `sshpass` 以支持密码登录。
4.  **Git**: 项目必须是一个 Git 仓库。

## 配置说明 (Configuration)

在项目根目录下的 **统一 `.env`** 文件中配置。公共变量所有模块共享，差异化变量使用 `MODULE_<模块名>_` 前缀：

```bash
# ===== 公共配置 (所有模块共享) =====
ALIYUN_REGISTRY="registry.cn-hangzhou.aliyuncs.com"
ALIYUN_NAMESPACE="your-namespace"
ALIYUN_USER="your-username"
ALIYUN_PASSWORD="your-password"
REMOTE_USER="root"
REMOTE_HOST="your.server.ip"
REMOTE_PASSWORD="your-ssh-password"
REMOTE_DIR="/root"
GIT_COMMIT_ENABLED=false

# ===== 前端模块: frontend =====
MODULE_FRONTEND_IMAGE_NAME=crm-web
MODULE_FRONTEND_IMAGE_TAG=latest
MODULE_FRONTEND_BUILD_CMD=true
MODULE_FRONTEND_DOCKERFILE=./crm-web/Dockerfile
MODULE_FRONTEND_BUILD_CONTEXT=./crm-web
MODULE_FRONTEND_REMOTE_SCRIPT=./crm-web/remote_deploy.sh
MODULE_FRONTEND_BUILD_ENV=test
```

## 使用方法 (Usage)

在项目根目录下运行，传入模块名即可：

```bash
# 部署前端 (默认模块名 frontend)
.antigravity/skills/frontend-deploy/scripts/deploy.sh
.antigravity/skills/frontend-deploy/scripts/deploy.sh frontend

# 将来新增子模块时，只需在 .env 中添加 MODULE_XXX_ 变量，使用模块名部署
.antigravity/skills/frontend-deploy/scripts/deploy.sh admin-web
```

## 自定义 (Customization)

-   **构建命令 (Vue3)**:
    脚本会自动检测 `package.json`，默认使用 `npm run build`。
    如果你的项目使用 pnpm 或 yarn，可以在 `.env` 中设置：
    ```bash
    MODULE_FRONTEND_BUILD_CMD="pnpm build"
    ```

-   **构建环境变量**: 可设置 `MODULE_FRONTEND_BUILD_ENV` 来传递 `--build-arg BUILD_ENV` 给 Docker。

-   **远程脚本**: 可自定义 `MODULE_FRONTEND_REMOTE_SCRIPT` 指向各模块的远程部署脚本。
