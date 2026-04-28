# 前端自动部署 Skill 使用指南 (Vue3)

这是一个专为 Vue3 等前端项目设计的自动部署 Skill。

## 包含内容

-   **`skills/frontend-deploy/SKILL.md`**: 使用文档。
-   **`skills/frontend-deploy/scripts/deploy.sh`**: 部署脚本（针对前端构建优化）。
-   **`skills/frontend-deploy/scripts/remote_deploy_template.sh`**: 远程部署模板。

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
    REMOTE_PASSWORD=你的SSH密码 # 可选
    REMOTE_DIR=/root
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

2.  **构建命令**:
    脚本默认运行 `npm run build`。
    -   如果是 yarn 项目，会自动切换为 `yarn build`。
    -   如果是 pnpm 项目，会自动切换为 `pnpm build`。
    -   可通过 `MODULE_FRONTEND_BUILD_CMD` 自定义。

3.  **运行部署**:
    
    部署前端（默认模块名 `frontend`）：
    ```bash
    .antigravity/skills/frontend-deploy/scripts/deploy.sh
    .antigravity/skills/frontend-deploy/scripts/deploy.sh frontend
    ```

    **多模块部署**: 只需在 `.env` 中添加 `MODULE_<模块名>_` 前缀变量，然后指定模块名：
    ```bash
    .antigravity/skills/frontend-deploy/scripts/deploy.sh admin-web
    ```

## Dockerfile 建议

前端项目通常需要一个 Dockerfile 来构建 Nginx 镜像。示例如下：

```dockerfile
# Build Stage
FROM node:18 as build-stage
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Production Stage
FROM nginx:stable-alpine as production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```
