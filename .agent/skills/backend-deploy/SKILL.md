---
name: 后端自动部署 (Backend Auto-Deployment)
description: 自动化代码提交、构建、推送Docker镜像到阿里云镜像仓库，并执行远程服务器部署脚本。
---

# 后端自动部署 (Backend Auto-Deployment)

这个 Skill 旨在自动化后端服务的部署流程，主要包含以下步骤：
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

# ===== 后端模块: backend =====
MODULE_BACKEND_IMAGE_NAME=crm-service
MODULE_BACKEND_IMAGE_TAG=1.0.0
MODULE_BACKEND_PROFILES_ACTIVE=dev
MODULE_BACKEND_DOCKERFILE=./path/to/Dockerfile
MODULE_BACKEND_BUILD_CONTEXT=./path/to/context
MODULE_BACKEND_REMOTE_SCRIPT=./path/to/remote_deploy.sh
```

## 使用方法 (Usage)

在项目根目录下运行，传入模块名即可：

```bash
# 部署后端 (默认模块名 backend)
.antigravity/skills/backend-deploy/scripts/deploy.sh
.antigravity/skills/backend-deploy/scripts/deploy.sh backend

# 将来新增子模块时，只需在 .env 中添加 MODULE_XXX_ 变量，使用模块名部署
.antigravity/skills/backend-deploy/scripts/deploy.sh another-module
```

## 自定义 (Customization)

-   **构建命令 (对于 Java 项目)**:
    脚本会自动检测 `pom.xml`，默认使用 `mvn clean package -DskipTests`。
    如需自定义，在 `.env` 中设置模块级变量：
    ```bash
    MODULE_BACKEND_BUILD_CMD="mvn clean package -Pprod"
    ```

-   **远程脚本**: 可自定义 `MODULE_BACKEND_REMOTE_SCRIPT` 指向各模块的远程部署脚本。
