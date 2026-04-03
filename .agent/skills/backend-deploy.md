# 后端自动部署 Skill 使用指南

我为你创建了一个可复用的 **后端自动部署 Skill**，它可以自动化整个部署流程。

## 包含内容

-   **`skills/backend-deploy/SKILL.md`**: 使用文档和配置指南。
-   **`skills/backend-deploy/scripts/deploy.sh`**: 主部署脚本（自动处理 Mac -> Linux 的跨平台构建）。
-   **`skills/backend-deploy/scripts/remote_deploy_template.sh`**: 在远程服务器上执行的脚本模板。

## 如何使用

1.  **配置环境变量**:
    在项目根目录下的 **统一 `.env`** 文件中配置。公共变量所有模块共享，差异化变量使用 `MODULE_<模块名>_` 前缀：
    ```env
    # ===== 公共配置 (所有模块共享) =====
    ALIYUN_REGISTRY=registry.cn-hangzhou.aliyuncs.com
    ALIYUN_NAMESPACE=你的命名空间
    ALIYUN_USER=你的阿里云用户名
    ALIYUN_PASSWORD=你的阿里云密码
    REMOTE_USER=root
    REMOTE_HOST=你的服务器IP
    REMOTE_PASSWORD=你的SSH密码  # (可选)
    REMOTE_DIR=/root
    GIT_COMMIT_ENABLED=false

    # ===== 后端模块: backend =====
    MODULE_BACKEND_IMAGE_NAME=crm-service
    MODULE_BACKEND_IMAGE_TAG=1.0.0
    MODULE_BACKEND_PROFILES_ACTIVE=dev
    MODULE_BACKEND_DOCKERFILE=./path/to/Dockerfile
    MODULE_BACKEND_BUILD_CONTEXT=./path/to/context
    MODULE_BACKEND_REMOTE_SCRIPT=./path/to/deploy_docker.sh
    ```

    **注意**: 如果使用密码登录，请确保本地已安装 `sshpass` (macOS: `brew install sshpass`)。

2.  **自定义 (可选)**:
    -   如果构建命令不是默认的 `mvn clean package -DskipTests`，请设置模块级变量 `MODULE_BACKEND_BUILD_CMD`。
    -   如果你需要修改服务器上启动容器的方式（端口映射、挂载卷等），请修改 `REMOTE_SCRIPT` 指向的远程脚本。

3.  **运行部署**:
    
    部署后端（默认模块名 `backend`）：
    ```bash
    .antigravity/skills/backend-deploy/scripts/deploy.sh
    .antigravity/skills/backend-deploy/scripts/deploy.sh backend
    ```

    **多模块部署**: 只需在 `.env` 中添加 `MODULE_<模块名>_` 前缀变量，然后指定模块名：
    ```bash
    .antigravity/skills/backend-deploy/scripts/deploy.sh gateway
    .antigravity/skills/backend-deploy/scripts/deploy.sh user-service
    ```

    **Java / Maven 项目**:
    脚本会自动检测 `pom.xml` 并运行 `mvn clean package -DskipTests`。
    如需自定义，设置模块级变量：
    ```bash
    MODULE_BACKEND_BUILD_CMD="mvn clean package -Pprod -DskipTests"
    ```

## 验证
脚本已通过 `bash -n` 语法验证。请在本地环境中配置好凭据后进行测试运行。
