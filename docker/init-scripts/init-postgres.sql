-- AI业务中台 PostgreSQL 初始化脚本
-- 严格按照文档 4.1 节数据模型定义

-- 启用UUID扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 4.1.1 用户表 (users)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100),
    email VARCHAR(100),
    department VARCHAR(100),
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    password_hash VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_department ON users(department);

-- 4.1.2 系统适配器表 (system_adapters)
CREATE TABLE system_adapters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    type VARCHAR(50) NOT NULL,              -- ERP, CRM, OA 等
    endpoint VARCHAR(500) NOT NULL,
    auth_type VARCHAR(50),                  -- bearer, basic, oauth2 等
    config JSONB,                           -- 配置信息（含字段映射、认证等）
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_system_adapters_code ON system_adapters(code);

-- 4.1.3 任务表 (tasks)
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    source_system VARCHAR(50) NOT NULL,     -- 来源系统标识
    source_id VARCHAR(100) NOT NULL,        -- 源系统任务ID
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'normal',
    deadline TIMESTAMP WITH TIME ZONE,
    external_url VARCHAR(500),              -- 外部系统跳转链接
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tasks_user ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_source ON tasks(source_system, source_id);

-- 4.1.4 知识库文档表 (documents)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    content TEXT,
    category VARCHAR(100),
    tags JSONB DEFAULT '[]'::jsonb,
    source VARCHAR(100),
    chunk_count INTEGER DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_documents_category ON documents(category);
CREATE INDEX idx_documents_status ON documents(status);

-- 4.1.5 会话历史表 (conversations) — 每条消息独立行
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL,              -- user, assistant, system
    content TEXT NOT NULL,
    message_type VARCHAR(50),               -- text, ui_spec, error 等
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_user ON conversations(user_id);
CREATE INDEX idx_conversations_session ON conversations(session_id);
CREATE INDEX idx_conversations_created ON conversations(created_at DESC);

-- 4.1.6 审计日志表 (audit_logs)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trace_id VARCHAR(100),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    intent VARCHAR(50),                     -- knowledge, data_query, task_operation, chat
    model VARCHAR(100),                     -- 使用的模型名称
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    latency_ms INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'success',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_intent ON audit_logs(intent);
CREATE INDEX idx_audit_logs_trace ON audit_logs(trace_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);

-- 4.1.7 API密钥表 (api_keys) — 应用级密钥管理
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    permissions JSONB DEFAULT '[]'::jsonb,
    rate_limit INTEGER DEFAULT 100,
    expires_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_status ON api_keys(status);

-- 4.1.8 知识库表 (knowledge_bases) — 知识库元数据
CREATE TABLE knowledge_bases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL DEFAULT 'general',
    embedding_model VARCHAR(100) DEFAULT 'bge-m3',
    chunk_strategy VARCHAR(50) DEFAULT 'recursive',
    chunk_size INTEGER DEFAULT 512,
    chunk_overlap INTEGER DEFAULT 50,
    document_count INTEGER DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_knowledge_bases_type ON knowledge_bases(type);
CREATE INDEX idx_knowledge_bases_created_by ON knowledge_bases(created_by);

-- 4.1.9 工作流定义表 (workflows) — 自定义工作流记录
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    bpmn_xml TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_workflows_status ON workflows(status);
CREATE INDEX idx_workflows_category ON workflows(category);

-- 4.1.10 工作流执行表 (workflow_executions)
CREATE TABLE workflow_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    initiator_id UUID REFERENCES users(id) ON DELETE SET NULL,
    current_node VARCHAR(200),
    variables JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_workflow_executions_workflow ON workflow_executions(workflow_id);
CREATE INDEX idx_workflow_executions_initiator ON workflow_executions(initiator_id);
CREATE INDEX idx_workflow_executions_status ON workflow_executions(status);

-- 4.1.11 智能体配置表 (agents)
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL DEFAULT 'assistant',
    model VARCHAR(100) NOT NULL DEFAULT 'qwen2.5:7b',
    system_prompt TEXT,
    tools JSONB DEFAULT '[]'::jsonb,
    temperature NUMERIC(3,2) DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 2048,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agents_type ON agents(type);
CREATE INDEX idx_agents_status ON agents(status);

-- 4.1.12 成本日志表 (cost_logs) — 用于 ClickHouse 同步
CREATE TABLE cost_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trace_id VARCHAR(100),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    model VARCHAR(100),
    provider VARCHAR(50),
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd NUMERIC(10,6) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cost_logs_user ON cost_logs(user_id);
CREATE INDEX idx_cost_logs_model ON cost_logs(model);
CREATE INDEX idx_cost_logs_created ON cost_logs(created_at DESC);

-- 插入默认管理员用户
INSERT INTO users (username, display_name, department, role, password_hash)
VALUES ('admin', '系统管理员', '技术部', 'admin', '$2a$10$wqv0yGZrxhgbf28pQ5e0..lBqFaUG2RglN6E466zvWXTjhFRrM8Dm');

-- 插入系统适配器预置数据
INSERT INTO system_adapters (name, code, type, endpoint, auth_type, config, status)
VALUES
    ('ERP系统', 'erp', 'ERP', 'http://erp.internal/api', 'bearer', '{"responsePath": "data.tasks", "taskFields": {"sourceId": "order_no", "title": "subject"}}', 'active'),
    ('CRM系统', 'crm', 'CRM', 'http://crm.internal/api', 'bearer', '{"responsePath": "data.list", "taskFields": {"sourceId": "opportunity_id", "title": "task_name"}}', 'active'),
    ('OA系统', 'oa', 'OA', 'http://oa.internal/api', 'bearer', '{"responsePath": "data.items", "taskFields": {"sourceId": "flow_id", "title": "flow_title"}}', 'active'),
    ('预约系统', 'reservation', 'RESERVATION', 'http://reservation.internal/api', 'api_key', '{"responsePath": "data.bookings", "taskFields": {"sourceId": "reservation_id", "title": "service_name"}}', 'active'),
    ('业务中台', 'biz_center', 'BIZ_CENTER', 'http://biz-center.internal/api', 'bearer', '{"responsePath": "data.tasks", "taskFields": {"sourceId": "task_id", "title": "task_name"}}', 'active'),
    ('360系统', 'system360', 'SYSTEM360', 'http://360.internal/api', 'bearer', '{"responsePath": "data.records", "taskFields": {"sourceId": "record_id", "title": "item_title"}}', 'active');
