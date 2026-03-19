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

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"

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

    # 外部LLM API
    openai_api_key: str = ""
    openai_base_url: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
