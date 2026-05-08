-- UI Builder / JSON Render 配置中心
-- 用途：存储接口源、接口定义、语义字典、运行日志、卡片和卡片接口关系

CREATE TABLE IF NOT EXISTS ui_api_sources (
    id              VARCHAR(64) PRIMARY KEY COMMENT '主键',
    name            VARCHAR(128) NOT NULL COMMENT '接口源名称',
    code            VARCHAR(64) NOT NULL COMMENT '接口源编码',
    description     VARCHAR(255) NULL COMMENT '接口源说明',
    source_type     VARCHAR(32) NOT NULL COMMENT '来源类型: openapi/manual/postman',
    base_url        VARCHAR(255) NULL COMMENT '服务基础地址',
    doc_url         VARCHAR(255) NULL COMMENT '接口文档地址',
    auth_type       VARCHAR(32) NOT NULL COMMENT '认证方式',
    auth_config     JSON NULL COMMENT '认证配置',
    default_headers JSON NULL COMMENT '默认请求头',
    env             VARCHAR(32) NOT NULL DEFAULT 'dev' COMMENT '环境: dev/test/prod',
    status          VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '状态',
    created_by      VARCHAR(64) NULL COMMENT '创建人',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_ui_api_sources_code (code),
    KEY idx_ui_api_sources_env_status (env, status)
) COMMENT='UI Builder 接口源';

CREATE TABLE IF NOT EXISTS ui_api_tags (
    id              VARCHAR(64) PRIMARY KEY COMMENT '主键',
    source_id       VARCHAR(64) NOT NULL COMMENT '所属接口源ID',
    name            VARCHAR(128) NOT NULL COMMENT '标签名称',
    code            VARCHAR(128) NOT NULL COMMENT '标签编码',
    description     VARCHAR(255) NULL COMMENT '标签说明',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_ui_api_tags_source_code (source_id, code),
    KEY idx_ui_api_tags_source (source_id)
) COMMENT='UI Builder 接口标签';

CREATE TABLE IF NOT EXISTS ui_api_endpoints (
    id                   VARCHAR(64) PRIMARY KEY COMMENT '主键',
    source_id            VARCHAR(64) NOT NULL COMMENT '接口源ID',
    tag_id               VARCHAR(64) NULL COMMENT '标签ID',
    name                 VARCHAR(128) NOT NULL COMMENT '接口名称',
    path                 VARCHAR(255) NOT NULL COMMENT '接口路径',
    method               VARCHAR(16) NOT NULL COMMENT 'HTTP方法',
    operation_safety     VARCHAR(16) NOT NULL DEFAULT 'query' COMMENT '操作安全等级: query/list/mutation',
    summary              VARCHAR(255) NULL COMMENT '接口摘要',
    request_content_type VARCHAR(64) NULL COMMENT '请求内容类型',
    request_schema       JSON NULL COMMENT '请求Schema',
    response_schema      JSON NULL COMMENT '响应Schema',
    sample_request       JSON NULL COMMENT '样例请求',
    sample_response      JSON NULL COMMENT '样例响应',
    field_orchestration  JSON NULL COMMENT '字段编排配置',
    status               VARCHAR(32) NOT NULL DEFAULT 'active' COMMENT '状态',
    created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY idx_ui_api_endpoints_source (source_id),
    KEY idx_ui_api_endpoints_tag (tag_id),
    KEY idx_ui_api_endpoints_method_path (method, path)
) COMMENT='UI Builder 接口定义';

CREATE TABLE IF NOT EXISTS ui_api_endpoint_roles (
    id               VARCHAR(64) PRIMARY KEY COMMENT '主键',
    endpoint_id      VARCHAR(64) NOT NULL COMMENT '接口定义ID',
    role_id          VARCHAR(64) NOT NULL COMMENT '角色ID',
    role_code        VARCHAR(128) NULL COMMENT '角色编码',
    role_name        VARCHAR(128) NOT NULL COMMENT '角色名称',
    field_orchestration JSON NULL COMMENT '字段编排配置',
    created_by       VARCHAR(64) NULL COMMENT '创建人',
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_ui_api_endpoint_roles_endpoint_role (endpoint_id, role_id),
    KEY idx_ui_api_endpoint_roles_role (role_id),
    KEY idx_ui_api_endpoint_roles_endpoint (endpoint_id)
) COMMENT='UI Builder 接口与角色关系';

CREATE TABLE IF NOT EXISTS semantic_field_dict (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    standard_key  VARCHAR(64)  NOT NULL UNIQUE COMMENT '标准字段key，如 gender',
    label         VARCHAR(64)  NOT NULL COMMENT '展示名，如 性别',
    field_type    VARCHAR(32)  NOT NULL COMMENT '组件类型，如 text/select/date/number',
    category      VARCHAR(64)  NULL COMMENT '业务域，如 user/order/product',
    value_map     JSON NULL COMMENT '全局值映射',
    description   TEXT NULL COMMENT '字段语义描述，给 AI 作为上下文使用',
    is_active     TINYINT      NOT NULL DEFAULT 1 COMMENT '是否启用',
    created_at    DATETIME NULL COMMENT '创建时间',
    updated_at    DATETIME NULL COMMENT '更新时间'
) COMMENT='语义字段字典主表';

CREATE TABLE IF NOT EXISTS semantic_field_alias (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    standard_key  VARCHAR(64)  NOT NULL COMMENT '关联 standard_key',
    alias         VARCHAR(64)  NOT NULL COMMENT '接口原始字段名',
    api_id        VARCHAR(64)  NOT NULL COMMENT '绑定接口ID',
    source        VARCHAR(16)  NULL COMMENT '来源：manual/ai',
    created_at    DATETIME NULL COMMENT '创建时间',
    UNIQUE KEY uk_alias_api (alias, api_id),
    KEY idx_semantic_field_alias_standard_key (standard_key),
    KEY idx_semantic_field_alias_api_id (api_id)
) COMMENT='语义字段别名表';

CREATE TABLE IF NOT EXISTS semantic_field_value_map (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    standard_key    VARCHAR(64)  NOT NULL COMMENT '关联 standard_key',
    api_id          VARCHAR(64)  NULL COMMENT 'NULL=全局，有值=接口级覆盖',
    standard_value  VARCHAR(64)  NOT NULL COMMENT '标准值（前端用）',
    raw_value       VARCHAR(64)  NOT NULL COMMENT '接口原始值',
    sort_order      INT          NOT NULL DEFAULT 0 COMMENT '排序号',
    UNIQUE KEY uk_value_api (standard_key, api_id, raw_value),
    KEY idx_semantic_field_value_map_standard_key (standard_key),
    KEY idx_semantic_field_value_map_api_id (api_id)
) COMMENT='语义字段值映射扩展表';

CREATE TABLE IF NOT EXISTS ui_api_test_logs (
    id               VARCHAR(64) PRIMARY KEY COMMENT '主键',
    endpoint_id      VARCHAR(64) NOT NULL COMMENT '接口ID',
    request_url      VARCHAR(255) NOT NULL COMMENT '调用地址',
    request_headers  JSON NULL COMMENT '请求头',
    request_query    JSON NULL COMMENT 'Query参数',
    request_body     JSON NULL COMMENT '请求体',
    response_status  INT NULL COMMENT '响应状态码',
    response_headers JSON NULL COMMENT '响应头',
    response_body    JSON NULL COMMENT '响应体',
    success_flag     TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否成功',
    error_message    VARCHAR(500) NULL COMMENT '错误信息',
    created_by       VARCHAR(64) NULL COMMENT '发起人',
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_ui_api_test_logs_endpoint_created (endpoint_id, created_at)
) COMMENT='UI Builder 接口联调日志';

CREATE TABLE IF NOT EXISTS ui_api_flow_logs (
    id               VARCHAR(64) PRIMARY KEY COMMENT '主键',
    flow_num         VARCHAR(64) NOT NULL COMMENT '流程编号',
    endpoint_id      VARCHAR(64) NOT NULL COMMENT '接口定义ID',
    request_url      VARCHAR(500) NOT NULL COMMENT '实际请求地址',
    request_headers  JSON NULL COMMENT '请求头',
    request_query    JSON NULL COMMENT '请求参数',
    request_body     JSON NULL COMMENT '请求体',
    response_status  INT NULL COMMENT 'HTTP响应状态码',
    response_headers JSON NULL COMMENT '响应头',
    response_body    JSON NULL COMMENT '响应体',
    invoke_status    VARCHAR(32) NOT NULL DEFAULT 'success' COMMENT '接口调用状态',
    error_message    VARCHAR(1000) NULL COMMENT '错误信息',
    created_by       VARCHAR(64) NULL COMMENT '创建人ID',
    created_by_name  VARCHAR(64) NULL COMMENT '创建人名称',
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY idx_ui_api_flow_logs_flow_created (flow_num, created_at),
    KEY idx_ui_api_flow_logs_endpoint_created (endpoint_id, created_at),
    KEY idx_ui_api_flow_logs_status_created (invoke_status, created_at)
) COMMENT='UI Builder 运行时接口调用日志';

DROP TABLE IF EXISTS ui_spec_versions;
DROP TABLE IF EXISTS ui_node_bindings;
DROP TABLE IF EXISTS ui_page_nodes;
DROP TABLE IF EXISTS ui_pages;
DROP TABLE IF EXISTS ui_projects;

CREATE TABLE IF NOT EXISTS ui_cards (
    id           VARCHAR(64) PRIMARY KEY COMMENT '主键',
    name         VARCHAR(128) NOT NULL COMMENT '卡片名称',
    code         VARCHAR(64) NOT NULL COMMENT '卡片编码',
    description  VARCHAR(255) NULL COMMENT '卡片说明',
    card_type    VARCHAR(32) NOT NULL DEFAULT 'json_render' COMMENT '卡片类型',
    status       VARCHAR(32) NOT NULL DEFAULT 'active' COMMENT '状态',
    created_by   VARCHAR(64) NULL COMMENT '创建人',
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_ui_cards_code (code),
    KEY idx_ui_cards_status (status)
) COMMENT='UI Builder 卡片定义';

CREATE TABLE IF NOT EXISTS ui_card_endpoint_relations (
    id           VARCHAR(64) PRIMARY KEY COMMENT '主键',
    card_id      VARCHAR(64) NOT NULL COMMENT '卡片ID',
    endpoint_id  VARCHAR(64) NOT NULL COMMENT '接口定义ID',
    sort_order   INT NOT NULL DEFAULT 0 COMMENT '排序',
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_ui_card_endpoint_relation (card_id, endpoint_id),
    KEY idx_ui_card_endpoint_relations_card_sort (card_id, sort_order),
    KEY idx_ui_card_endpoint_relations_endpoint (endpoint_id)
) COMMENT='UI Builder 卡片接口关系';
