from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    app_debug: bool = True
    app_port: int = 8000

    # MySQL
    database_url: str = "mysql+aiomysql://ai_platform:ai_platform_dev@localhost:3306/ai_platform?charset=utf8mb4"

    # Redis
    redis_url: str = "redis://:redis_dev@localhost:6379/0"

    # Milvus
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "knowledge_chunks"
    milvus_vector_field: str = "embedding"
    milvus_output_fields: list[str] = ["doc_id", "title", "content", "doc_type", "metadata"]
    milvus_search_limit: int = Field(20, ge=1, le=100)

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_username: str = "elastic"
    elasticsearch_password: str = "elastic_dev"
    elasticsearch_index: str = "knowledge_documents"

    # GraphRAG融合权重
    rag_vector_weight: float = Field(0.4, ge=0.0, le=1.0)
    rag_keyword_weight: float = Field(0.3, ge=0.0, le=1.0)
    rag_graph_weight: float = Field(0.3, ge=0.0, le=1.0)

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin_dev"

    # ClickHouse
    clickhouse_url: str = "http://localhost:8123"
    clickhouse_db: str = "ai_platform_logs"
    clickhouse_rag_table: str = "rag_metrics"

    # Neo4j
    neo4j_uri: str = "neo4j://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j"

    # Embedding & Reranker
    embedding_model_name: str = "BAAI/bge-m3"
    reranker_model_name: str = "BAAI/bge-reranker-large"
    rag_rerank_limit: int = 8

    # Text2SQL
    text2sql_default_database: str = "default"
    text2sql_timeout_seconds: int = 12
    text2sql_max_rows: int = 200

    # 动态UI
    llm_ui_spec_enabled: bool = False

    # Intent classification
    intent_confidence_threshold: float = Field(0.55, ge=0.0, le=1.0)

    # 业务编排层
    business_server_url: str = "http://localhost:8080"

    # 外部LLM API
    openai_api_key: str = ""
    openai_base_url: str = ""

    # LangSmith 可观测性
    langsmith_api_key: str = ""
    langsmith_project: str = "ai-platform"
    langsmith_tracing: bool = False

    # RabbitMQ（缓存失效监听）
    rabbitmq_url: str = "amqp://admin:admin_dev@localhost:5672/"

    # Feature Flags（本地模式，key=flag名, value=bool）
    feature_flags: dict[str, bool] = {
        "semantic-cache": False,
        "spring-ai": False,
    }

    # 语义缓存（S5-11）
    semantic_cache_enabled: bool = False
    semantic_cache_similarity_threshold: float = 0.95
    semantic_cache_ttl_hours: int = 24
    semantic_cache_max_size: int = 10000

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
