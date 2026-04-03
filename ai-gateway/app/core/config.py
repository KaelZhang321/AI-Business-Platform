from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    app_debug: bool = True
    app_port: int = 8000

    # MySQL
    ai_mysql_host: str = "localhost"
    ai_mysql_port: int = 3306
    ai_mysql_user: str = "ai_platform"
    ai_mysql_password: str = "ai_platform_dev"
    ai_mysql_database: str = "ai_platform"

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
    text2sql_api_key: str = ""          # ARK / OpenAI API Key（env: TEXT2SQL_API_KEY 或 ARK_API_KEY）
    text2sql_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    text2sql_model: str = "ep-20251108132803-xbb9f"

    # Meeting BI
    meeting_bi_enabled: bool = False
    meeting_bi_database_url: str = "mysql+pymysql://root:root@localhost:3306/meeting_bi?charset=utf8mb4"
    meeting_bi_api_key: str = ""
    meeting_bi_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    meeting_bi_model: str = "deepseek-v3-2-251201"
    meeting_bi_max_rows: int = 200
    meeting_bi_context_ttl_seconds: int = 1800
    meeting_bi_train_on_startup: bool = False

    # 动态UI
    llm_ui_spec_enabled: bool = False

    # API Query Stage-2
    api_query_route_timeout_seconds: float = 8.0
    api_query_route_retry_count: int = 1
    api_query_retrieval_timeout_seconds: float = 0.8
    api_query_retrieval_per_domain_top_k: int = 2
    api_query_score_threshold: float = 0.3

    # Intent classification
    intent_confidence_threshold: float = Field(0.55, ge=0.0, le=1.0)

    # 业务编排层
    business_server_url: str = "http://localhost:8080"
    business_server_timeout_seconds: float = 15.0

    # 身份金库
    identity_vault_enabled: bool = True
    gateway_jwt_secret: str = ""

    # API Registry / UI Builder metadata
    api_catalog_source_mode: str = "hybrid"  # yaml | ui_builder | hybrid
    ui_builder_metadata_timeout_seconds: float = 10.0
    ui_builder_metadata_page_size: int = 100
    ui_builder_metadata_token: str = ""

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
