# Build stage
FROM crpi-301jbh81iyvo39lb.cn-beijing.personal.cr.aliyuncs.com/leczcore_prod/node:20-alpine as builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
# Add build argument for environment, default to 'pro'
ARG BUILD_ENV=pro
RUN npm run build:${BUILD_ENV}

# Production stage
FROM crpi-301jbh81iyvo39lb.cn-beijing.personal.cr.aliyuncs.com/leczcore_prod/nginx:stable-alpine as production

ENV TZ=Asia/Shanghai

# Nginx 容器日志默认依赖系统时区，显式安装 tzdata 可避免多容器时间轴错位。
RUN apk add --no-cache tzdata && \
    ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime && \
    echo "${TZ}" >/etc/timezone

COPY --from=builder /app/dist /usr/share/nginx/html
COPY default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
