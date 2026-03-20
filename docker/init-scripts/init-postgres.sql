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
    user_id UUID REFERENCES users(id),
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
    user_id UUID NOT NULL REFERENCES users(id),
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
    user_id UUID REFERENCES users(id),
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

-- 插入默认管理员用户
INSERT INTO users (username, display_name, department, role, password_hash)
VALUES ('admin', '系统管理员', '技术部', 'admin', '$2a$10$wqv0yGZrxhgbf28pQ5e0..lBqFaUG2RglN6E466zvWXTjhFRrM8Dm');
