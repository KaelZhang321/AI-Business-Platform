# AI业务中台

企业级AI业务中台，集成多源系统数据与AI能力，提供统一的智能工作台。

## 技术架构

| 层级 | 技术栈 | 路径 |
|------|--------|------|
| 前端 (T5/T6) | React 18 + Vite + TypeScript + Ant Design 5 | `frontend/` |
| AI网关 (T4.1) | Python FastAPI + LangChain + LangGraph | `ai-gateway/` |
| 业务编排 (T2/T4.2) | Java Spring Boot 3.x + MyBatis-Plus | `business-server/` |
| 基础设施 | PostgreSQL, Redis, Milvus, RabbitMQ, ES, MinIO | `docker/` |

## 快速启动

### 1. 启动基础设施

```bash
cd docker
cp .env.example .env
docker compose up -d
```

### 2. 启动 AI 网关

```bash
cd ai-gateway
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

访问 http://localhost:8000/docs 查看 API 文档。

### 3. 启动业务编排层

```bash
cd business-server
mvn spring-boot:run
```

服务运行在 http://localhost:8080

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

## 服务端口

| 服务 | 端口 |
|------|------|
| 前端 | 5173 |
| AI网关 | 8000 |
| 业务编排层 | 8080 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Milvus | 19530 |
| RabbitMQ | 5672 / 15672 (管理界面) |
| Elasticsearch | 9200 |
| MinIO | 9000 / 9001 (控制台) |
| Ollama | 11434 |

## 项目文档

详细架构设计文档见 `docs/` 目录。
