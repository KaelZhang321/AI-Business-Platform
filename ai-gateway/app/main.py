from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, knowledge, query
from app.core.config import settings
from app.models.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化资源
    yield
    # 关闭时清理资源


app = FastAPI(
    title="AI业务中台 - AI网关",
    description="企业级AI网关服务，提供对话、知识检索、Text2SQL等能力",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/v1", tags=["对话"])
app.include_router(knowledge.router, prefix="/api/v1", tags=["知识库"])
app.include_router(query.router, prefix="/api/v1", tags=["数据查询"])


@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    return HealthResponse(
        status="ok",
        version="0.1.0",
        services={"database": "unchecked", "redis": "unchecked", "milvus": "unchecked"},
    )
