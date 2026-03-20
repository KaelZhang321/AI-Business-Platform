# AI业务中台 (AI Business Platform)

企业级AI业务中台，集成多源系统数据与AI能力，提供统一的智能工作台。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Java](https://img.shields.io/badge/Java-17-blue.svg)](https://www.oracle.com/java/)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-cyan.svg)](https://reactjs.org/)

## 🎯 项目简介

本项目是一个**面向企业的AI集成平台**，旨在通过AI技术打通企业内部分离的各个业务系统（ERP、CRM、OA等），实现：

- **统一工作台**：一个界面聚合所有待办事项，无需切换多个系统
- **智能问答**：基于RAG技术的私有知识库问答
- **自然语言查询**：通过Text2SQL用自然语言查询业务数据
- **动态UI生成**：AI实时生成匹配的后台管理界面

## 🏗️ 技术架构

### 系统分层

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端层 (Frontend)                        │
│              React 18 + Vite + TypeScript + Ant Design          │
│                         端口: 5173                                │
└─────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
┌─────────────────────────────────┐  ┌─────────────────────────────────┐
│        AI网关层 (AI Gateway)      │  │     业务编排层 (Business Server)  │
│   Python/FastAPI + LangChain     │  │      Java/Spring Boot 3         │
│         端口: 8000               │  │          端口: 8080              │
└─────────────────────────────────┘  └─────────────────────────────────┘
          │                                    │
          ▼                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                       基础设施层 (Infrastructure)                 │
│   PostgreSQL │ Redis │ Milvus │ RabbitMQ │ Elasticsearch │ MinIO │
└─────────────────────────────────────────────────────────────────┘
```

### 请求流向

```
前端(:5173) ──→ AI网关(:8000)     ──→ Ollama / Milvus / ES / ClickHouse
              └→ 业务编排(:8080)   ──→ PostgreSQL / Redis / RabbitMQ
```

## ✨ 核心功能

### 1. 🤖 多系统适配器架构
- 抽象统一的 `BaseSystemAdapter` 接口
- 已实现：ERP适配器、CRM适配器、OA适配器
- 支持快速扩展新系统对接

### 2. 🔍 RAG 智能问答
- 混合检索：向量相似度 + 关键词BM25 + RRF融合
- 支持多文档格式：PDF、Word、Markdown、TXT
- 向量数据库：Milvus
- 文档解析：Unstructured OCR

### 3. 📊 Text2SQL 自然语言查询
- 基于 Vanna.ai 实现
- 自动生成SQL语句查询业务数据库
- 支持复杂Join和聚合查询

### 4. 🎨 动态UI生成
- AI根据业务数据动态渲染管理界面
- 支持7种核心组件类型
- 实时交互，无需重复开发

### 5. 📝 AI对话助手
- SSE流式响应
- 意图自动分类与路由
- 会话历史持久化

### 6. 📋 审计日志
- 完整的AI调用记录
- 请求参数、响应内容、耗时分析
- 合规审计支持

## 🛠️ 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **前端** | React 18 + Vite 5 + TypeScript 5 | 现代前端工程化 |
| **UI框架** | Ant Design 5 + Tailwind CSS | 企业级组件库 |
| **状态管理** | Zustand | 轻量级状态管理 |
| **AI网关** | Python 3.11+ / FastAPI | 高性能异步API |
| **AI框架** | LangChain 0.3 + LangGraph 0.2 | LLM应用开发框架 |
| **LLM** | Ollama (本地部署) | 私有化部署保护数据安全 |
| **向量库** | Milvus | 高性能向量检索 |
| **业务编排** | Java 17 / Spring Boot 3.3 | 企业级Java开发 |
| **ORM** | MyBatis-Plus 3.5.9 | 敏捷数据库操作 |
| **消息队列** | RabbitMQ | 异步任务解耦 |
| **缓存** | Redis | 高性能缓存 |
| **搜索引擎** | Elasticsearch | 全文检索 |
| **对象存储** | MinIO | S3兼容对象存储 |
| **数据库** | PostgreSQL | 关系型数据存储 |
| **分析引擎** | ClickHouse | OLAP数据分析 |
| **基础设施** | Docker Compose | 容器化编排 |

## 📁 项目结构

```
AI业务中台/
├── frontend/                          # React 前端应用
│   ├── src/
│   │   ├── components/                # 组件库
│   │   │   ├── chat/                 # AI对话组件 (assistant-ui)
│   │   │   └── dynamic-ui/           # 动态UI渲染引擎
│   │   ├── layouts/                  # 布局组件
│   │   ├── pages/                    # 页面
│   │   │   ├── Workspace/            # 统一工作台
│   │   │   └── KnowledgeBase/        # 知识库管理
│   │   ├── stores/                   # Zustand状态管理
│   │   ├── services/                # API服务层
│   │   └── types/                    # TypeScript类型定义
│   └── vite.config.ts                # Vite配置(含代理)
│
├── ai-gateway/                        # Python AI网关
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/              # API路由
│   │   │       ├── chat.py           # 对话接口(SSE)
│   │   │       ├── knowledge.py      # 知识库接口
│   │   │       └── query.py          # Text2SQL接口
│   │   ├── services/                 # 业务服务
│   │   │   ├── intent_classifier.py  # 意图分类
│   │   │   ├── rag_service.py         # RAG服务
│   │   │   ├── text2sql_service.py   # Text2SQL服务
│   │   │   └── dynamic_ui_service.py  # 动态UI服务
│   │   ├── models/                   # 数据模型
│   │   └── core/                     # 核心配置
│   └── pyproject.toml                 # Python依赖
│
├── business-server/                    # Java 业务编排层
│   ├── src/main/java/com/lzke/ai/
│   │   ├── controller/               # REST控制器
│   │   │   ├── TaskController.java   # 待办任务
│   │   │   ├── KnowledgeController.java # 知识库
│   │   │   └── AuditController.java  # 审计日志
│   │   ├── service/                 # 业务服务层
│   │   ├── adapter/                  # 系统适配器
│   │   │   ├── BaseSystemAdapter.java
│   │   │   ├── ErpAdapter.java
│   │   │   ├── CrmAdapter.java
│   │   │   └── OaAdapter.java
│   │   ├── mapper/                  # MyBatis Mapper
│   │   ├── model/
│   │   │   ├── entity/              # 实体类
│   │   │   ├── dto/                  # 请求DTO
│   │   │   └── vo/                   # 响应VO
│   │   └── config/                   # 配置类
│   └── pom.xml                       # Maven依赖
│
├── docker/                            # 基础设施
│   ├── docker-compose.yml            # 服务编排
│   └── init-scripts/
│       └── init-postgres.sql         # 数据库初始化
│
└── docs/                              # 架构设计文档
    ├── AI业务中台_整体技术架构文档.md
    └── AI业务中台_MVP一期实施文档.md
```

## 🚀 快速开始

### 环境要求

| 工具 | 版本要求 |
|------|---------|
| Node.js | 18+ |
| Python | 3.11+ |
| JDK | **17** (必须) |
| Maven | 3.9+ |
| Docker | 24+ |

> ⚠️ **JDK 注意**：Lombok 不兼容 JDK 23+，请确保使用 JDK 17

### 步骤 1：启动基础设施

```bash
cd docker
cp .env.example .env
docker compose up -d
```

### 步骤 2：启动 AI 网关

```bash
cd ai-gateway
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

访问 http://localhost:8000/docs 查看 Swagger API 文档

### 步骤 3：启动业务编排层

```bash
cd business-server
# 设置JDK 17路径（如需要）
export JAVA_HOME=/path/to/jdk17
mvn spring-boot:run
```

服务运行在 http://localhost:8080

### 步骤 4：启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 进入统一工作台

## 🌐 服务端口一览

| 服务 | 端口 | 用途 |
|------|------|------|
| 前端 | 5173 | Web UI |
| AI网关 | 8000 | LLM推理、RAG |
| 业务编排 | 8080 | 业务API |
| PostgreSQL | 5432 | 主数据库 |
| Redis | 6379 | 缓存/会话 |
| Milvus | 19530 | 向量存储 |
| RabbitMQ | 5672/15672 | 消息队列 |
| Elasticsearch | 9200 | 全文搜索 |
| MinIO | 9000/9001 | 对象存储 |
| ClickHouse | 8123 | OLAP分析 |
| Ollama | 11434 | 本地LLM |

## 📡 API 文档

### AI网关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/chat` | SSE流式对话 |
| POST | `/api/v1/knowledge/search` | RAG混合检索 |
| POST | `/api/v1/query/text2sql` | 自然语言转SQL |
| GET | `/health` | 健康检查 |

### 业务编排 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/tasks/aggregate` | 多系统待办聚合 |
| POST | `/api/v1/knowledge/documents` | 上传知识文档 |
| GET | `/api/v1/knowledge/documents` | 查询文档列表 |
| GET | `/api/v1/audit/logs` | 审计日志查询 |

## 📊 数据库设计

6张核心表存储在 `docker/init-scripts/init-postgres.sql`：

| 表名 | 用途 |
|------|------|
| `users` | 用户信息 |
| `system_adapters` | 系统适配器配置 |
| `tasks` | 待办任务（多系统聚合） |
| `documents` | 知识库文档 |
| `conversations` | AI对话历史 |
| `audit_logs` | 审计日志 |

## 📚 文档

详细架构设计文档请参考 `docs/` 目录：

- `AI业务中台_整体技术架构文档.md` — 完整技术架构设计
- `AI业务中台_MVP一期实施文档.md` — 项目实施计划与接口规范

## 📄 License

MIT License - 详见 [LICENSE](LICENSE) 文件
