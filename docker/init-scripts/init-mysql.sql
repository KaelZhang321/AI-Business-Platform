-- AI业务中台 MySQL 8.0 初始化脚本
-- 严格按照文档 4.1 节数据模型定义

-- 4.1.1 用户表 (users)
CREATE TABLE users (
    id CHAR(36) NOT NULL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100),
    email VARCHAR(100),
    department VARCHAR(100),
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    password_hash VARCHAR(255) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_department ON users(department);

-- 4.1.2 系统适配器表 (system_adapters)
CREATE TABLE system_adapters (
    id CHAR(36) NOT NULL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    type VARCHAR(50) NOT NULL,
    endpoint VARCHAR(500) NOT NULL,
    auth_type VARCHAR(50),
    config JSON,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_system_adapters_code ON system_adapters(code);

-- 4.1.3 任务表 (tasks)
CREATE TABLE tasks (
    id CHAR(36) NOT NULL PRIMARY KEY,
    user_id CHAR(36),
    source_system VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'normal',
    deadline DATETIME,
    external_url VARCHAR(500),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_tasks_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_tasks_user ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_source ON tasks(source_system, source_id);

-- 4.1.4 知识库文档表 (documents)
CREATE TABLE documents (
    id CHAR(36) NOT NULL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    category VARCHAR(100),
    tags JSON DEFAULT (JSON_ARRAY()),
    source VARCHAR(100),
    chunk_count INT DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_documents_category ON documents(category);
CREATE INDEX idx_documents_status ON documents(status);

-- 4.1.5 会话历史表 (conversations)
CREATE TABLE conversations (
    id CHAR(36) NOT NULL PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    message_type VARCHAR(50),
    metadata JSON,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_conversations_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_conversations_user ON conversations(user_id);
CREATE INDEX idx_conversations_session ON conversations(session_id);
CREATE INDEX idx_conversations_created ON conversations(created_at DESC);

-- 4.1.6 审计日志表 (audit_logs)
CREATE TABLE audit_logs (
    id CHAR(36) NOT NULL PRIMARY KEY,
    trace_id VARCHAR(100),
    user_id CHAR(36),
    intent VARCHAR(50),
    model VARCHAR(100),
    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    latency_ms INT,
    status VARCHAR(20) NOT NULL DEFAULT 'success',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_logs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_intent ON audit_logs(intent);
CREATE INDEX idx_audit_logs_trace ON audit_logs(trace_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);

-- 4.1.7 API密钥表 (api_keys)
CREATE TABLE api_keys (
    id CHAR(36) NOT NULL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    user_id CHAR(36),
    permissions JSON DEFAULT (JSON_ARRAY()),
    rate_limit INT DEFAULT 100,
    expires_at DATETIME,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    last_used_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_api_keys_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_status ON api_keys(status);

-- 4.1.8 知识库表 (knowledge_bases)
CREATE TABLE knowledge_bases (
    id CHAR(36) NOT NULL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL DEFAULT 'general',
    embedding_model VARCHAR(100) DEFAULT 'bge-m3',
    chunk_strategy VARCHAR(50) DEFAULT 'recursive',
    chunk_size INT DEFAULT 512,
    chunk_overlap INT DEFAULT 50,
    document_count INT DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by CHAR(36),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_knowledge_bases_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_knowledge_bases_type ON knowledge_bases(type);
CREATE INDEX idx_knowledge_bases_created_by ON knowledge_bases(created_by);

-- 4.1.9 工作流定义表 (workflows)
CREATE TABLE workflows (
    id CHAR(36) NOT NULL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    bpmn_xml TEXT,
    version INT NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_by CHAR(36),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_workflows_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_workflows_status ON workflows(status);
CREATE INDEX idx_workflows_category ON workflows(category);

-- 4.1.10 工作流执行表 (workflow_executions)
CREATE TABLE workflow_executions (
    id CHAR(36) NOT NULL PRIMARY KEY,
    workflow_id CHAR(36) NOT NULL,
    initiator_id CHAR(36),
    current_node VARCHAR(200),
    variables JSON DEFAULT (JSON_OBJECT()),
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_wf_exec_workflow FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
    CONSTRAINT fk_wf_exec_initiator FOREIGN KEY (initiator_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_workflow_executions_workflow ON workflow_executions(workflow_id);
CREATE INDEX idx_workflow_executions_initiator ON workflow_executions(initiator_id);
CREATE INDEX idx_workflow_executions_status ON workflow_executions(status);

-- 4.1.11 智能体配置表 (agents)
CREATE TABLE agents (
    id CHAR(36) NOT NULL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL DEFAULT 'assistant',
    model VARCHAR(100) NOT NULL DEFAULT 'qwen2.5:7b',
    system_prompt TEXT,
    tools JSON DEFAULT (JSON_ARRAY()),
    temperature DECIMAL(3,2) DEFAULT 0.70,
    max_tokens INT DEFAULT 2048,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by CHAR(36),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agents_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_agents_type ON agents(type);
CREATE INDEX idx_agents_status ON agents(status);

-- 4.1.12 成本日志表 (cost_logs)
CREATE TABLE cost_logs (
    id CHAR(36) NOT NULL PRIMARY KEY,
    trace_id VARCHAR(100),
    user_id CHAR(36),
    model VARCHAR(100),
    provider VARCHAR(50),
    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    cost_usd DECIMAL(10,6) DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cost_logs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_cost_logs_user ON cost_logs(user_id);
CREATE INDEX idx_cost_logs_model ON cost_logs(model);
CREATE INDEX idx_cost_logs_created ON cost_logs(created_at DESC);

-- 插入默认管理员用户
INSERT INTO users (id, username, display_name, department, role, password_hash)
VALUES (UUID(), 'admin', '系统管理员', '技术部', 'admin', '$2a$10$wqv0yGZrxhgbf28pQ5e0..lBqFaUG2RglN6E466zvWXTjhFRrM8Dm');

-- 插入系统适配器预置数据
INSERT INTO system_adapters (id, name, code, type, endpoint, auth_type, config, status)
VALUES
    (UUID(), 'ERP系统', 'erp', 'ERP', 'http://erp.internal/api', 'bearer', '{"responsePath": "data.tasks", "taskFields": {"sourceId": "order_no", "title": "subject"}}', 'active'),
    (UUID(), 'CRM系统', 'crm', 'CRM', 'http://crm.internal/api', 'bearer', '{"responsePath": "data.list", "taskFields": {"sourceId": "opportunity_id", "title": "task_name"}}', 'active'),
    (UUID(), 'OA系统', 'oa', 'OA', 'http://oa.internal/api', 'bearer', '{"responsePath": "data.items", "taskFields": {"sourceId": "flow_id", "title": "flow_title"}}', 'active'),
    (UUID(), '预约系统', 'reservation', 'RESERVATION', 'http://reservation.internal/api', 'api_key', '{"responsePath": "data.bookings", "taskFields": {"sourceId": "reservation_id", "title": "service_name"}}', 'active'),
    (UUID(), '业务中台', 'biz_center', 'BIZ_CENTER', 'http://biz-center.internal/api', 'bearer', '{"responsePath": "data.tasks", "taskFields": {"sourceId": "task_id", "title": "task_name"}}', 'active'),
    (UUID(), '360系统', 'system360', 'SYSTEM360', 'http://360.internal/api', 'bearer', '{"responsePath": "data.records", "taskFields": {"sourceId": "record_id", "title": "item_title"}}', 'active');
