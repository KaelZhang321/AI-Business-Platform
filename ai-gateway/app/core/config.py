from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    app_debug: bool = True
    app_port: int = 8000

    # Business MySQL
    # ai-gateway 直连的治理元数据和问数库统一收敛到业务库配置，避免维护第二套网关专属 MySQL 变量。
    business_mysql_host: str = Field(default="localhost")
    business_mysql_port: int = Field(default=3306)
    business_mysql_user: str = Field(default="ai_platform")
    business_mysql_password: str = Field(default="ai_platform_dev")
    business_mysql_database: str = Field(default="ai_platform_business")

    # Health Quadrant ODS MySQL
    health_quadrant_ods_mysql_host: str = Field(default="rm-2ze7k76808sos442l.mysql.rds.aliyuncs.com")
    health_quadrant_ods_mysql_port: int = Field(default=3306)
    health_quadrant_ods_mysql_user: str = Field(default="pro_platform")
    health_quadrant_ods_mysql_password: str = Field(default="xxxxxxxxx")
    health_quadrant_ods_mysql_database: str = Field(default="dc_ods")
    health_quadrant_mysql_connect_timeout_seconds: float = Field(5.0, ge=0.1, le=60.0)
    dw_route_url: str = Field(default="http://127.0.0.1:8085/api/v1")

    # Redis
    redis_url: str = "redis://:redis_dev@localhost:6379/0"

    # Milvus
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "api_catalog"
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
    embedding_model_path: str = ""
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
    # 详情页模板优先策略总开关：
    # - false: 全量走 dynamic_ui 详情渲染（不下发 templateCode）
    # - true: 下发 template_first 策略（templateCode/fallbackMode 由目录 hint 提供）
    api_query_template_first_enabled: bool = False
    # 多步骤查询渲染策略：
    # - auto_result: 自动在 terminal / aggregate 间切换（推荐默认值）
    # - terminal_result/composite_result: 兼容旧值，运行期会自动归一到 auto_result
    # - aggregate_result: 同屏聚合展示所有叶子业务步骤
    # - summary_table: 仅展示执行步骤汇总
    api_query_multi_step_render_policy: str = "auto_result"

    # API Query 专用 LLM（Volcengine Ark）
    # 这一组配置只服务 `/api/v1/api-query`，避免把网关内其他问答/聊天链路强行绑到同一供应商。
    ark_api_key: str = ""
    ark_api_base: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_default_model: str = "doubao-1-5-pro-32k-250115"

    # Runtime LLM 配置（MySQL 驱动）
    llm_runtime_config_table: str = "llm_service_backend_config"
    llm_runtime_config_cache_ttl_seconds: int = Field(60, ge=1, le=3600)
    smart_meal_risk_llm_timeout_seconds: float = Field(120.0, ge=0.1, le=600.0)
    smart_meal_recommend_llm_timeout_seconds: float = Field(120.0, ge=0.1, le=600.0)

    # API Query Stage-2
    api_query_route_timeout_seconds: float = 60.0
    api_query_route_retry_count: int = 1
    api_query_retrieval_timeout_seconds: float = 0.8
    api_query_retrieval_per_domain_top_k: int = 2
    # 第二阶段默认改为 0.4，是为了更贴近设计文档中的“宁可少给候选，也不喂垃圾接口”的保守策略。
    api_query_score_threshold: float = 0.4
    api_query_runtime_invoke_url_template: str = (
        "https://beta-ai-platform.kaibol.net/ai-platform/api/v1/ui-builder/runtime/endpoints/{id}/invoke"
        # "http://39.96.197.81:8080/api/v1/ui-builder/runtime/endpoints/{id}/invoke"
    )
    api_query_runtime_flow_num: int = 1212
    api_query_runtime_created_by: str = ""
    api_query_runtime_timeout_seconds: float = 60.0
    api_query_runtime_enabled: bool = True
    api_query_execution_max_step_count: int = Field(8, ge=1, le=50)
    api_query_execution_step_timeout_seconds: float = Field(600.0, ge=0.1, le=600.0)
    api_query_execution_graph_timeout_seconds: float = Field(30.0, ge=0.1, le=120.0)
    api_query_execution_min_step_budget_seconds: float = Field(5, ge=0.1, le=10.0)

    # Intent classification
    intent_confidence_threshold: float = Field(0.55, ge=0.0, le=1.0)

    # 业务编排层
    business_server_url: str = "http://localhost:8080"
    business_server_timeout_seconds: float = 15.0

    # API Catalog Indexer
    api_catalog_mysql_connect_timeout_seconds: float = Field(5.0, ge=0.1, le=60.0)
    api_catalog_milvus_connect_timeout_seconds: float = Field(5.0, ge=0.1, le=60.0)

    # API Catalog GraphRAG
    # 这一组配置集中承载 GraphRAG 的运行时护栏，避免后续 graph sync / retriever / validator
    # 在各自 service 里继续散落 ad-hoc 常量，导致灰度和降级行为难以统一。
    api_catalog_graph_enabled: bool = False
    api_catalog_graph_expand_hops: int = Field(1, ge=1, le=3)
    api_catalog_graph_anchor_top_k: int = Field(3, ge=1, le=10)
    api_catalog_graph_support_limit: int = Field(12, ge=1, le=100)
    api_catalog_graph_validation_enabled: bool = False
    api_catalog_graph_strict_for_mutation: bool = True
    api_catalog_graph_cache_enabled: bool = False
    api_catalog_graph_cache_ttl_seconds: int = Field(21600, ge=1, le=86400)
    api_catalog_graph_field_degree_cutoff: int = Field(50, ge=1, le=10000)
    api_catalog_graph_related_domain_enabled: bool = True
    api_catalog_interaction_snapshot_ttl_seconds: int = Field(1800, ge=30, le=86400)
    api_catalog_graph_cache_singleflight_ttl_seconds: int = Field(15, ge=1, le=300)

    # 身份金库
    identity_vault_enabled: bool = True
    gateway_jwt_secret: str = ""

    # 外部LLM API
    openai_api_key: str = ""
    openai_base_url: str = ""
    # 默认为 False：避免开发机/容器继承到脏代理变量后把模型请求错误转发到代理。
    model_router_trust_env: bool = False

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
