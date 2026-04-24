# 优化方案10：API版本管理与消息格式统一规范

> 解决问题：仅提URL路径版本化，缺少Breaking Change策略；MCP/SSE/WebSocket消息格式不统一
> 优先级：P2（中优先级，Q2-Q3解决）
> 工作量：1天设计 + 1天实现
> 影响范围：全产品线API调用与通信

---

## 一、API版本管理策略

### 1.1 版本化规则

```
URL路径版本化（已确定）：
  /api/v1/models
  /api/v2/models

版本号语义：
  v{major} — 仅大版本号，不使用minor/patch

大版本变更条件（Breaking Change）：
  - 删除API端点
  - 删除请求/响应字段
  - 修改字段类型或语义
  - 修改认证方式
  - 修改错误码含义

非Breaking Change（不升级版本）：
  - 新增API端点
  - 新增可选请求字段
  - 新增响应字段
  - 新增错误码
  - 性能/内部实现优化
```

### 1.2 多版本并行策略

```
┌──────────────────────────────────────────────┐
│           API版本生命周期                      │
│                                               │
│  状态流转：                                    │
│  CURRENT → DEPRECATED → SUNSET → REMOVED     │
│                                               │
│  ┌──────────┬──────────┬──────────┐          │
│  │ v1       │ v2       │ v3       │          │
│  │ DEPRECATED│ CURRENT  │ BETA     │          │
│  │ 6个月后   │ 生产版本  │ 预览版本  │          │
│  │ SUNSET   │          │          │          │
│  └──────────┴──────────┴──────────┘          │
│                                               │
│  并行规则：                                    │
│  - 最多同时维护 2个正式版本（N和N-1）           │
│  - DEPRECATED版本保留 ≥6个月                   │
│  - SUNSET前至少提前 3个月发布迁移指南            │
│  - BETA版本不保证向后兼容                       │
└──────────────────────────────────────────────┘
```

### 1.3 版本升级通知机制

```java
// API网关 - 版本检测拦截器
@Component
public class ApiVersionInterceptor implements HandlerInterceptor {

    @Override
    public boolean preHandle(HttpServletRequest request,
                              HttpServletResponse response,
                              Object handler) {
        String path = request.getRequestURI();
        String version = extractVersion(path); // 提取 "v1", "v2" 等

        ApiVersionStatus status = versionRegistry.getStatus(version);

        switch (status) {
            case CURRENT:
                break; // 正常处理
            case DEPRECATED:
                response.setHeader("X-API-Deprecated", "true");
                response.setHeader("X-API-Sunset-Date", "2026-09-30");
                response.setHeader("X-API-Migration-Guide",
                    "/docs/migration/v1-to-v2");
                // 记录使用已废弃API的调用方
                auditLog.logDeprecatedUsage(request);
                break;
            case SUNSET:
                response.setStatus(410); // Gone
                response.getWriter().write(
                    "{\"error\":\"API version sunset\",\"migration\":\"/docs/migration\"}");
                return false;
            case BETA:
                response.setHeader("X-API-Beta", "true");
                break;
        }
        return true;
    }
}
```

### 1.4 SDK版本对应关系

| P8中台版本 | API版本 | Java SDK | Python SDK | 前端SDK |
|-----------|---------|----------|------------|--------|
| v0.5 | v1 | 1.0.x | 1.0.x | 1.0.x |
| v1.0 | v1 | 1.1.x | 1.1.x | 1.1.x |
| v1.5 | v1 | 1.2.x | 1.2.x | 1.2.x |
| v2.0 | v2（Breaking） | 2.0.x | 2.0.x | 2.0.x |
| v2.5 | v2 | 2.1.x | 2.1.x | 2.1.x |
| v3.0 | v2 | 2.2.x | 2.2.x | 2.2.x |

**预计v1→v2 Breaking Change**：
- 新增多模态输入格式（v2.0）
- Agent API重构（v2.0）
- Function Calling协议升级（v2.0）

---

## 二、统一消息信封规范

### 2.1 消息信封结构

```typescript
// 所有通信协议的统一消息信封
interface MessageEnvelope<T = unknown> {
  // 元数据
  version: string;          // 协议版本："1.0"
  id: string;               // 消息唯一ID（UUID v7）
  traceId: string;          // 链路追踪ID（OpenTelemetry Trace ID）
  timestamp: number;        // 毫秒时间戳

  // 路由信息
  source: string;           // 来源服务："p8-gateway", "p2-doctor", "p6-wework"
  target?: string;          // 目标服务（可选，广播时为空）
  type: MessageType;        // 消息类型

  // 业务数据
  payload: T;               // 业务载荷（泛型）

  // 上下文
  context?: {
    userId?: string;        // 用户ID
    tenantId?: string;      // 租户ID（预留多租户）
    sessionId?: string;     // 会话ID
    locale?: string;        // 语言："zh-CN"
  };
}

type MessageType =
  // 请求/响应
  | "REQUEST"
  | "RESPONSE"
  | "ERROR"
  // 流式
  | "STREAM_START"
  | "STREAM_CHUNK"
  | "STREAM_END"
  | "STREAM_ERROR"
  // 事件
  | "EVENT"
  | "NOTIFICATION"
  // 控制
  | "HEARTBEAT"
  | "ACK";
```

### 2.2 各协议消息格式映射

#### HTTP REST API

```json
// 请求 → 标准JSON
POST /api/v1/ai/chat
{
  "version": "1.0",
  "id": "msg_01927e3c-4d2f-7000-8abc-def012345678",
  "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
  "timestamp": 1710000000000,
  "source": "p2-doctor",
  "type": "REQUEST",
  "payload": {
    "model": "deepseek-v3",
    "messages": [{"role": "user", "content": "..."}],
    "stream": false
  },
  "context": {
    "userId": "doctor_001",
    "sessionId": "sess_abc123"
  }
}

// 响应
{
  "version": "1.0",
  "id": "msg_01927e3c-5a1f-7000-9abc-fed987654321",
  "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
  "timestamp": 1710000001500,
  "source": "p8-gateway",
  "type": "RESPONSE",
  "payload": {
    "content": "根据患者症状...",
    "model": "deepseek-v3",
    "usage": {"prompt_tokens": 150, "completion_tokens": 200}
  }
}
```

#### SSE 流式输出

```
// Server-Sent Events 格式
// 每个event遵循统一信封，payload为增量内容

event: STREAM_START
data: {"version":"1.0","id":"msg_001","traceId":"abc","timestamp":1710000000000,"source":"p8-gateway","type":"STREAM_START","payload":{"model":"deepseek-v3","sessionId":"sess_001"}}

event: STREAM_CHUNK
data: {"version":"1.0","id":"msg_002","traceId":"abc","timestamp":1710000000100,"source":"p8-gateway","type":"STREAM_CHUNK","payload":{"delta":"根据"}}

event: STREAM_CHUNK
data: {"version":"1.0","id":"msg_003","traceId":"abc","timestamp":1710000000200,"source":"p8-gateway","type":"STREAM_CHUNK","payload":{"delta":"患者症状"}}

event: STREAM_END
data: {"version":"1.0","id":"msg_004","traceId":"abc","timestamp":1710000001500,"source":"p8-gateway","type":"STREAM_END","payload":{"usage":{"prompt_tokens":150,"completion_tokens":200},"finishReason":"stop"}}
```

#### WebSocket 双向通信

```json
// WebSocket帧 - 与HTTP信封完全一致
// 客户端发送
{
  "version": "1.0",
  "id": "msg_005",
  "traceId": "def",
  "timestamp": 1710000002000,
  "source": "p2-doctor",
  "type": "REQUEST",
  "payload": {
    "action": "subscribe",
    "channel": "patient_alerts",
    "patientId": "pt_001"
  }
}

// 服务端推送通知
{
  "version": "1.0",
  "id": "msg_006",
  "traceId": "ghi",
  "timestamp": 1710000003000,
  "source": "p8-notification",
  "type": "NOTIFICATION",
  "payload": {
    "level": "WARNING",
    "title": "药物相互作用提醒",
    "content": "阿司匹林与华法林存在相互作用风险",
    "action": {"type": "NAVIGATE", "target": "/prescription/review/123"}
  }
}

// 心跳
{
  "version": "1.0",
  "id": "msg_007",
  "timestamp": 1710000004000,
  "source": "p2-doctor",
  "type": "HEARTBEAT",
  "payload": {}
}
```

#### RabbitMQ 异步消息

```json
// MQ消息体 - 同样遵循统一信封
{
  "version": "1.0",
  "id": "msg_008",
  "traceId": "jkl",
  "timestamp": 1710000005000,
  "source": "p3-nursing",
  "target": "p8-ai-gateway",
  "type": "EVENT",
  "payload": {
    "event": "VITAL_SIGN_ABNORMAL",
    "patientId": "pt_002",
    "data": {
      "heartRate": 120,
      "bloodPressure": "160/100",
      "temperature": 38.5
    }
  },
  "context": {
    "userId": "nurse_001",
    "tenantId": "lizkal"
  }
}
```

### 2.3 错误格式统一

```typescript
// 统一错误信封
interface ErrorPayload {
  code: number;          // HTTP状态码 或 业务错误码
  error: string;         // 错误类型："VALIDATION_ERROR" | "AUTH_ERROR" | ...
  message: string;       // 用户可读的错误描述
  details?: object;      // 详细错误信息（开发环境可见）
  retryable: boolean;    // 是否可重试
  retryAfter?: number;   // 重试等待秒数（限流场景）
}
```

**业务错误码规范**：

| 码段 | 模块 | 示例 |
|------|------|------|
| 1000-1999 | 通用错误 | 1001 参数校验失败 |
| 2000-2999 | 认证授权 | 2001 Token过期、2002 权限不足 |
| 3000-3999 | AI模型 | 3001 模型不可用、3002 上下文超限、3003 内容安全拦截 |
| 4000-4999 | 知识库 | 4001 知识库不存在、4002 文档解析失败 |
| 5000-5999 | 工作流 | 5001 工作流执行超时、5002 节点执行失败 |
| 6000-6999 | 业务规则 | 6001 配伍禁忌、6002 剂量超限 |
| 7000-7999 | 外部系统 | 7001 HIS连接超时、7002 LIS接口异常 |

---

## 三、API文档规范

### 3.1 OpenAPI 3.1规范

```yaml
# 所有API必须使用OpenAPI 3.1描述
openapi: "3.1.0"
info:
  title: "丽滋卡尔AI中台API"
  version: "1.0.0"
  description: "P8 AI技术中台统一API"

servers:
  - url: https://ai-api.lizkal.com/api/v1
    description: 生产环境
  - url: https://ai-api-staging.lizkal.com/api/v1
    description: 预发布环境

# 通用响应头
components:
  headers:
    X-Request-Id:
      description: 请求唯一ID
      schema: { type: string }
    X-Trace-Id:
      description: 链路追踪ID
      schema: { type: string }
    X-RateLimit-Remaining:
      description: 剩余调用次数
      schema: { type: integer }
    X-API-Deprecated:
      description: API废弃标记
      schema: { type: boolean }
```

### 3.2 文档自动生成

| 工具 | 用途 | 配置 |
|------|------|------|
| Springdoc OpenAPI | Java API → OpenAPI 3.1 | Spring Boot插件 |
| FastAPI auto-docs | Python API → OpenAPI 3.1 | FastAPI内置 |
| Swagger UI | API文档展示 | /api/docs 路径 |
| Redoc | API文档静态站点 | CI/CD自动构建 |

---

## 四、执行检查清单

- [ ] 发布API版本管理规范文档
- [ ] 实现ApiVersionInterceptor（废弃版本HTTP Header提醒）
- [ ] 定义v1→v2 Breaking Change清单（配合P8 v2.0规划）
- [ ] 制定统一消息信封TypeScript+Java类型定义
- [ ] SSE流式输出改造为统一信封格式
- [ ] WebSocket消息改造为统一信封格式
- [ ] RabbitMQ消息体改造为统一信封格式
- [ ] 统一错误码表发布到Wiki
- [ ] Springdoc + Swagger UI集成到P8网关
- [ ] API文档CI/CD自动构建流程
