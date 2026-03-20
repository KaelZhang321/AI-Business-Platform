from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    app_debug: bool = True
    app_port: int = 8000

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://ai_platform:ai_platform_dev@localhost:5432/ai_platform"

    # Redis
    redis_url: str = "redis://:redis_dev@localhost:6379/0"

    # Milvus
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "knowledge_chunks"
    milvus_vector_field: str = "embedding"
    milvus_output_fields: list[str] = ["doc_id", "title", "content", "doc_type", "metadata"]
    milvus_search_limit: int = 20

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "knowledge_documents"

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

    # 外部LLM API
    openai_api_key: str = ""
    openai_base_url: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
