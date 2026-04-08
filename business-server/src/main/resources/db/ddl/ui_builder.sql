-- UI Builder / JSON Render 配置中心
-- 用途：存储接口源、接口定义、页面节点、字段绑定和最终生成的 json-render spec

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
    created_by       VARCHAR(64) NULL COMMENT '创建人',
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_ui_api_endpoint_roles_endpoint_role (endpoint_id, role_id),
    KEY idx_ui_api_endpoint_roles_role (role_id),
    KEY idx_ui_api_endpoint_roles_endpoint (endpoint_id)
) COMMENT='UI Builder 接口与角色关系';

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

CREATE TABLE IF NOT EXISTS ui_projects (
    id           VARCHAR(64) PRIMARY KEY COMMENT '主键',
    name         VARCHAR(128) NOT NULL COMMENT '项目名称',
    code         VARCHAR(64) NOT NULL COMMENT '项目编码',
    description  VARCHAR(255) NULL COMMENT '项目说明',
    category     VARCHAR(64) NULL COMMENT '项目分类',
    status       VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '状态',
    created_by   VARCHAR(64) NULL COMMENT '创建人',
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_ui_projects_code (code),
    KEY idx_ui_projects_status (status)
) COMMENT='UI Builder 项目';

CREATE TABLE IF NOT EXISTS ui_pages (
    id            VARCHAR(64) PRIMARY KEY COMMENT '主键',
    project_id    VARCHAR(64) NOT NULL COMMENT '所属项目ID',
    name          VARCHAR(128) NOT NULL COMMENT '页面名称',
    code          VARCHAR(64) NOT NULL COMMENT '页面编码',
    title         VARCHAR(128) NULL COMMENT '页面标题',
    route_path    VARCHAR(128) NULL COMMENT '前端访问路径',
    root_node_id  VARCHAR(64) NULL COMMENT '根节点ID',
    layout_type   VARCHAR(32) NOT NULL DEFAULT 'page' COMMENT '布局类型',
    status        VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '状态',
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_ui_pages_code (code),
    KEY idx_ui_pages_project (project_id)
) COMMENT='UI Builder 页面';

CREATE TABLE IF NOT EXISTS ui_page_nodes (
    id            VARCHAR(64) PRIMARY KEY COMMENT '主键',
    page_id        VARCHAR(64) NOT NULL COMMENT '页面ID',
    parent_id      VARCHAR(64) NULL COMMENT '父节点ID',
    node_key       VARCHAR(64) NOT NULL COMMENT '最终spec中的element key',
    node_type      VARCHAR(32) NOT NULL COMMENT '节点类型',
    node_name      VARCHAR(128) NOT NULL COMMENT '节点名称',
    sort_order     INT NOT NULL DEFAULT 0 COMMENT '排序号',
    slot_name      VARCHAR(32) NOT NULL DEFAULT 'default' COMMENT '槽位',
    props_config   JSON NULL COMMENT '静态props配置',
    style_config   JSON NULL COMMENT '样式配置',
    status         VARCHAR(32) NOT NULL DEFAULT 'active' COMMENT '状态',
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_ui_page_nodes_page_key (page_id, node_key),
    KEY idx_ui_page_nodes_parent_sort (parent_id, sort_order),
    KEY idx_ui_page_nodes_page_type (page_id, node_type)
) COMMENT='UI Builder 页面节点';

CREATE TABLE IF NOT EXISTS ui_node_bindings (
    id               VARCHAR(64) PRIMARY KEY COMMENT '主键',
    node_id           VARCHAR(64) NOT NULL COMMENT '节点ID',
    endpoint_id       VARCHAR(64) NULL COMMENT '接口ID',
    binding_type      VARCHAR(32) NOT NULL DEFAULT 'static' COMMENT '绑定类型',
    target_prop       VARCHAR(128) NOT NULL COMMENT '目标属性路径，如 value、option.series',
    source_path       VARCHAR(255) NULL COMMENT '来源路径，如 $.data.totalRevenue',
    transform_script  TEXT NULL COMMENT '转换脚本/表达式',
    default_value     JSON NULL COMMENT '默认值',
    required_flag     TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否必填',
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY idx_ui_node_bindings_node (node_id),
    KEY idx_ui_node_bindings_endpoint (endpoint_id)
) COMMENT='UI Builder 节点字段绑定';

CREATE TABLE IF NOT EXISTS ui_spec_versions (
    id              VARCHAR(64) PRIMARY KEY COMMENT '主键',
    project_id       VARCHAR(64) NOT NULL COMMENT '项目ID',
    page_id          VARCHAR(64) NOT NULL COMMENT '页面ID',
    version_no       INT NOT NULL COMMENT '版本号',
    publish_status   VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '发布状态',
    spec_content     JSON NOT NULL COMMENT '最终 json-render spec',
    source_snapshot  JSON NULL COMMENT '生成时的配置快照',
    published_by     VARCHAR(64) NULL COMMENT '发布人',
    published_at     TIMESTAMP NULL COMMENT '发布时间',
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY uk_ui_spec_versions_page_version (page_id, version_no),
    KEY idx_ui_spec_versions_project_page (project_id, page_id)
) COMMENT='UI Builder 生成版本';
