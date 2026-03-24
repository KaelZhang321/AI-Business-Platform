# AI业务中台 - MVP一期实施文档

> **文档版本**：V1.0
> **编制时间**：2026年3月19日
> **编制部门**：AI部门
> **适用范围**：MVP一期研发实施
> **密级**：内部机密

---

## 目录

1. [MVP范围定义](#一mvp范围定义)
2. [技术架构](#二技术架构)
3. [功能详细设计](#三功能详细设计)
4. [数据模型](#四数据模型)
5. [接口设计](#五接口设计)
6. [实施计划](#六实施计划)
7. [验收标准](#七验收标准)

---

## 一、MVP范围定义

### 1.1 MVP核心功能

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **F1 统一工作台** | 统一入口，整合所有业务系统待办和数据查询 | P0 |
| **F2 AI对话助手** | 自然语言交互的AI助手（assistant-ui） | P0 |
| **F3 知识问答** | RAG文档问答，知识库检索 | P0 |
| **F4 数据查询** | Text2SQL自然语言查数（Vanna.ai） | P0 |
| **F5 动态UI渲染** | AI生成UI组件（json-render） | P0 |
| **F6 待办聚合** | 整合ERP/CRM/OA等系统待办任务 | P1 |
| **F7 系统数据查询** | 各业务系统数据统一查询入口 | P1 |

### 1.2 MVP不包含范围

- P1-P5五个岗位AI工作台的具体业务功能
- 企微侧边栏（独立部署）
- 工作流平台（后续迭代）
- 智能体平台（后续迭代）
- 评测监控平台（后续迭代）

### 1.3 用户故事

```
【用户故事 1】作为员工，我希望能在一个入口查看所有待办任务
    场景：打开工作台，看到ERP待办、CRM待办、OA待办聚合在一起
    验收：能查看所有来源的待办，能跳转到原系统处理

【用户故事 2】作为员工，我想用自然语言查询数据
    场景：问"本月新增客户有哪些？"，系统返回数据表格
    验收：能正确转换为SQL，能展示结果

【用户故事 3】作为员工，我想问关于公司制度的问题
    场景：问"年假怎么算？"，系统从知识库检索并回答
    验收：能准确检索，能提供答案来源

【用户故事 4】作为员工，我想通过对话完成业务操作
    场景：说"帮我查一下张三的档案"，系统展示客户卡片
    验收：能展示结构化数据，能自然语言交互

【用户故事 5】作为管理员，我想能看到AI使用统计
    场景：查看日活跃用户、问数统计、模型调用量
    验收：能看到基础运营数据
```

---

## 二、技术架构

### 2.1 MVP技术架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              【前端】React + Vite                              │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  assistant-ui (AI对话)  │  json-render (动态UI)  │  Ant Design (组件) │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │ HTTP/WebSocket
┌───────────────────────────────────────▼─────────────────────────────────────┐
│                         【AI网关层】Python FastAPI                           │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
│  │  Intent Router   │  │   RAG Service    │  │  Text2SQL Service│       │
│  │  (意图路由)       │  │  (知识检索)       │  │  (Vanna.ai)       │       │
│  │  - 意图分类      │  │  - Milvus检索    │  │  - SQL生成        │       │
│  │  - 任务分发      │  │  - 混合检索      │  │  - 结果转换       │       │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘       │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                              │
│  │   LLM Service    │  │  DynamicUI Gen   │                              │
│  │  (大模型服务)    │  │  (动态UI生成)    │                              │
│  │  - Ollama/Qwen2.5│  │  - json-spec输出 │                              │
│  │  - 模型路由      │  │  - 流式渲染      │                              │
│  └──────────────────┘  └──────────────────┘                              │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │ HTTP/gRPC
┌───────────────────────────────────────▼─────────────────────────────────────┐
│                        【业务编排层】Java Spring Boot                         │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
│  │  TaskAggregator   │  │  DataQuery       │  │  SystemAdapter    │       │
│  │  (待办聚合)       │  │  (数据查询)       │  │  (系统适配器)     │       │
│  │  - 多系统聚合     │  │  - SQL执行        │  │  - ERP Adapter    │       │
│  │  - 统一格式化     │  │  - 结果转换       │  │  - CRM Adapter    │       │
│  └──────────────────┘  └──────────────────┘  │  - OA Adapter     │       │
│                                                └──────────────────┘       │
│  ┌──────────────────┐  ┌──────────────────┐                              │
│  │  KnowledgeService│  │  AuditService    │                              │
│  │  (知识服务)      │  │  (审计服务)      │                              │
│  │  - 文档管理      │  │  - 调用日志      │                              │
│  │  - 知识检索      │  │  - 统计报表      │                              │
│  └──────────────────┘  └──────────────────┘                              │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼─────────────────────────────────────┐
│                         【系统集成层】Java Adapter                             │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ ERP系统     │  │ CRM系统     │  │ OA系统     │  │ 其他系统    │  │
│  │ (金蝶/用友) │  │ (销售易等) │  │ (泛微等)  │  │ (自研系统) │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流向

```
用户输入: "本月新增客户有哪些？"
    │
    ▼
意图分类 → data_query (数据查询)
    │
    ▼
Text2SQL → "SELECT * FROM customer WHERE created_at >= '2026-03-01'"
    │
    ▼
SQL执行 → 返回结果集
    │
    ▼
JSON Spec生成 → 
{
  "type": "Table",
  "props": { "columns": ["客户名称", "手机号", "创建时间"] },
  "data": [...]
}
    │
    ▼
json-render渲染 → 表格展示
```

---

## 三、功能详细设计

### 3.1 F1 统一工作台

#### 3.1.1 功能描述

聚合所有业务系统的待办任务，提供统一的任务入口。

#### 3.1.2 页面布局

```
┌─────────────────────────────────────────────────────────────────────────┐
│  丽滋卡尔AI工作台                                           [用户] [设置] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐  ┌───────────────────────────────────────────────┐  │
│  │                 │  │                                                │  │
│  │   AI对话区      │  │              动态内容区                        │  │
│  │                 │  │                                                │  │
│  │  [assistant-ui] │  │   ┌─────────────┐  ┌─────────────┐        │  │
│  │                 │  │   │  待办任务    │  │  数据查询   │        │  │
│  │                 │  │   │  ┌───────┐  │  │  ┌───────┐  │        │  │
│  │                 │  │   │  │ ERP 3 │  │  │  │ 客户   │  │        │  │
│  │                 │  │   │  │ CRM 5 │  │  │  │ 订单   │  │        │  │
│  │                 │  │   │  │ OA 2  │  │  │  │ 业绩   │  │        │  │
│  │                 │  │   │  └───────┘  │  │  └───────┘  │        │  │
│  │                 │  │   └─────────────┘  └───────────────┘        │  │
│  └─────────────────┘  └───────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 3.1.3 待办聚合逻辑

```java
@Service
public class TaskAggregatorService {
    
    public TaskVO aggregateTasks(String userId) {
        List<Task> allTasks = new ArrayList<>();
        
        // 并行调用各系统适配器
        CompletableFuture<List<Task>> erpTasks = 
            CompletableFuture.supplyAsync(() -> erpAdapter.getTasks(userId));
        CompletableFuture<List<Task>> crmTasks = 
            CompletableFuture.supplyAsync(() -> crmAdapter.getTasks(userId));
        CompletableFuture<List<Task>> oaTasks = 
            CompletableFuture.supplyAsync(() -> oaAdapter.getTasks(userId));
        
        // 合并结果
        allTasks.addAll(erpTasks.join());
        allTasks.addAll(crmTasks.join());
        allTasks.addAll(oaTasks.join());
        
        // 按截止时间排序
        allTasks.sort(Comparator.comparing(Task::getDeadline));
        
        return TaskVO.builder()
            .totalCount(allTasks.size())
            .tasks(allTasks)
            .sourceStats(calculateSourceStats(allTasks))
            .build();
    }
}
```

### 3.2 F2 AI对话助手

#### 3.2.1 功能描述

基于 assistant-ui 的专业AI对话界面，支持流式输出、多轮对话、Markdown渲染。

#### 3.2.2 组件配置

```typescript
// assistant-ui 配置
import { Chat, useEdgeRuntime } from "@assistant-ui/react";
import { useVercelStream } from "@assistant-ui/react";

function AIChat() {
  const runtime = useEdgeRuntime({
    api: "/api/chat",
  });

  return <Chat runtime={runtime} />;
}
```

#### 3.2.3 支持的对话场景

| 场景 | 示例 | 处理方式 |
|------|------|----------|
| 知识问答 | "公司年假怎么算？" | RAG检索 → 生成回答 |
| 数据查询 | "本月新增客户？" | Text2SQL → 表格展示 |
| 任务查询 | "我有几个待办？" | Task聚合 → 列表展示 |
| 系统操作 | "帮我查下张三档案" | 意图识别 → 动态UI |
| 闲聊 | "你好" | 直接回复 |

### 3.3 F3 知识问答（RAG）

#### 3.3.1 功能描述

基于RAG的企业知识库问答，支持混合检索（向量+关键词）。

#### 3.3.2 RAG Pipeline

```python
class RAGService:
    def __init__(self):
        self.embedder = OllamaEmbeddings(model="bge-m3")
        self.vector_store = Milvus(
            collection_name="knowledge_base",
            embedding_function=self.embedder
        )
        self.reranker = CohereRerank()
    
    def retrieve(self, query: str, top_k: int = 5):
        # 1. 向量检索
        vector_results = self.vector_store.similarity_search(
            query, 
            k=20
        )
        
        # 2. 关键词检索
        keyword_results = self.es.search(
            index="knowledge",
            query=query,
            size=20
        )
        
        # 3. 结果融合 (RRF)
        fused = self._reciprocal_rank_fusion(
            [vector_results, keyword_results],
            k=60
        )
        
        # 4. 重排序
        reranked = self.reranker.rerank(
            query=query,
            documents=fused,
            top_n=top_k
        )
        
        return reranked
    
    def chat(self, query: str) -> dict:
        # 检索
        docs = self.retrieve(query)
        
        # 构建上下文
        context = "\n\n".join([doc.content for doc in docs])
        
        # 生成回答
        prompt = f"""基于以下知识回答问题：
        
知识：
{context}

问题：{query}

回答："""
        
        response = self.llm.chat([
            {"role": "user", "content": prompt}
        ])
        
        return {
            "answer": response.content,
            "sources": [
                {"title": doc.title, "score": doc.score} 
                for doc in docs
            ]
        }
```

### 3.4 F4 数据查询（Text2SQL）

#### 3.4.1 功能描述

基于Vanna.ai的自然语言转SQL查询，支持多数据库。

#### 3.4.2 Vanna.ai集成

```python
from vanna.ai import VannaAI
from vanna.postgres import Postgres

class BIQueryService:
    def __init__(self, db_config: dict):
        self.vanna = VannaAI(
            model="qwen2.5",
            api_key=os.getenv("API_KEY")
        )
        self.db = Postgres(**db_config)
        self.vanna.connect_to_postgres(**db_config)
    
    def train(self, training_data: List[dict]):
        """训练：导入Schema和样例"""
        # 导入数据库Schema
        self.vanna.train(
            question="这个数据库有哪些表？",
            sql="SELECT table_name FROM information_schema.tables"
        )
        
        # 导入问答对
        for item in training_data:
            self.vanna.train(
                question=item["question"],
                sql=item["sql"]
            )
    
    def ask(self, question: str) -> dict:
        """自然语言查询"""
        # 生成SQL
        sql = self.vanna.ask(question)
        
        # 执行SQL（带安全检查）
        if self._is_safe_sql(sql):
            result = self.db.execute(sql)
        else:
            raise ValueError("SQL不安全")
        
        # 转换为JSON Spec
        return self._to_json_spec(result, question)
    
    def _to_json_spec(self, result: list, question: str) -> dict:
        """结果转换为json-render格式"""
        if not result:
            return {"type": "Text", "props": {"content": "没有查询到数据"}}
        
        columns = result[0].keys()
        return {
            "type": "Table",
            "props": {
                "columns": list(columns),
                "data": [list(row.values()) for row in result],
                "title": question
            }
        }
```

### 3.5 F5 动态UI渲染

#### 3.5.1 功能描述

基于json-render的动态UI生成，AI输出JSON Spec，前端渲染。

#### 3.5.2 组件目录定义

```typescript
// 定义UI组件目录
import { defineCatalog } from "@json-render/core";
import { schema } from "@json-render/react/schema";
import { z } from "zod";

const catalog = defineCatalog(schema, {
  components: {
    // 卡片组件
    Card: {
      props: z.object({
        title: z.string(),
        subtitle: z.string().optional(),
      }),
      description: "通用卡片容器"
    },
    
    // 表格组件
    Table: {
      props: z.object({
        columns: z.array(z.string()),
        data: z.array(z.array(z.any())),
        title: z.string().optional(),
      }),
      description: "数据表格"
    },
    
    // 指标卡组件
    Metric: {
      props: z.object({
        label: z.string(),
        value: z.string(),
        change: z.number().optional(),
        format: z.enum(["currency", "percent", "number"]).optional(),
      }),
      description: "指标展示卡片"
    },
    
    // 列表组件
    List: {
      props: z.object({
        items: z.array(z.object({
          id: z.string(),
          title: z.string(),
          description: z.string().optional(),
          status: z.string().optional(),
        })),
      }),
      description: "列表展示"
    },
    
    // 表单组件
    Form: {
      props: z.object({
        fields: z.array(z.object({
          name: z.string(),
          label: z.string(),
          type: z.enum(["text", "number", "date", "select"]),
          required: z.boolean(),
        })),
      }),
      description: "表单输入"
    },
    
    // 标签组件
    Tag: {
      props: z.object({
        label: z.string(),
        color: z.enum(["blue", "green", "red", "yellow"]).optional(),
      }),
      description: "状态标签"
    },
  },
  
  actions: {
    view_detail: { description: "查看详情" },
    refresh: { description: "刷新数据" },
    export: { description: "导出数据" },
  }
});

export { catalog };
```

#### 3.5.3 AI生成UI Spec

```python
class DynamicUIGenerator:
    SYSTEM_PROMPT = """你是一个专业的AI助手，擅长根据用户需求生成合适的UI组件。

可用组件：
- Card: 卡片，用于展示主题内容
- Table: 表格，用于展示列表数据
- Metric: 指标卡，用于展示单个数字指标
- List: 列表，用于展示待办/任务等
- Form: 表单，用于用户输入
- Tag: 标签，用于展示状态

根据用户意图和数据结构，选择最合适的组件组合来展示信息。
确保输出符合json-render规范的JSON Spec。

示例1（查询结果）：
输入：用户问"本月新增客户有哪些"，结果为客户列表
输出：
{
  "type": "Card",
  "props": {"title": "本月新增客户"},
  "children": [{
    "type": "Table",
    "props": {
      "columns": ["客户名称", "手机号", "创建时间"],
      "data": [["张三", "138****", "2026-03-01"]],
      "title": "客户列表"
    }
  }]
}

示例2（待办列表）：
输入：用户问"我的待办有哪些"
输出：
{
  "type": "List",
  "props": {
    "items": [
      {"id": "1", "title": "审批采购单", "description": "来自ERP", "status": "待处理"},
      {"id": "2", "title": "审核报告", "description": "来自CRM", "status": "待处理"}
    ]
  }
}
"""
    
    def generate(self, user_intent: str, data: dict) -> dict:
        """生成UI Spec"""
        prompt = f"""用户意图：{user_intent}
数据内容：{json.dumps(data, ensure_ascii=False)}

请生成合适的UI组件来展示这些信息。"""
        
        response = self.llm.chat([
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ])
        
        return json.loads(response.content)
```

---

## 四、数据模型

### 4.1 核心实体

#### 4.1.1 用户表 (user)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| username | VARCHAR(50) | 用户名 |
| display_name | VARCHAR(100) | 显示名称 |
| email | VARCHAR(100) | 邮箱 |
| department | VARCHAR(100) | 部门 |
| role | VARCHAR(50) | 角色 |
| status | VARCHAR(20) | 状态 |
| created_at | TIMESTAMP | 创建时间 |

#### 4.1.2 系统适配器表 (system_adapter)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | VARCHAR(100) | 系统名称 |
| code | VARCHAR(50) | 系统编码 |
| type | VARCHAR(50) | 类型(ERP/CRM/OA等) |
| endpoint | VARCHAR(500) | API地址 |
| auth_type | VARCHAR(50) | 认证方式 |
| config | JSONB | 配置信息 |
| status | VARCHAR(20) | 状态 |
| created_at | TIMESTAMP | 创建时间 |

#### 4.1.3 任务表 (task)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 用户ID |
| source_system | VARCHAR(50) | 来源系统 |
| source_id | VARCHAR(100) | 源系统任务ID |
| title | VARCHAR(500) | 任务标题 |
| description | TEXT | 任务描述 |
| status | VARCHAR(20) | 状态 |
| priority | VARCHAR(20) | 优先级 |
| deadline | TIMESTAMP | 截止时间 |
| external_url | VARCHAR(500) | 外部链接 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### 4.1.4 知识库文档表 (document)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| title | VARCHAR(500) | 文档标题 |
| content | TEXT | 文档内容 |
| category | VARCHAR(100) | 分类 |
| tags | JSONB | 标签 |
| source | VARCHAR(100) | 来源 |
| chunk_count | INTEGER | 分块数量 |
| status | VARCHAR(20) | 状态 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### 4.1.5 会话历史表 (conversation)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 用户ID |
| session_id | VARCHAR(100) | 会话ID |
| role | VARCHAR(20) | 角色(user/assistant) |
| content | TEXT | 内容 |
| message_type | VARCHAR(50) | 消息类型 |
| metadata | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |

#### 4.1.6 调用日志表 (audit_log)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| trace_id | VARCHAR(100) | 追踪ID |
| user_id | UUID | 用户ID |
| intent | VARCHAR(50) | 意图分类 |
| model | VARCHAR(100) | 使用模型 |
| input_tokens | INTEGER | 输入Token |
| output_tokens | INTEGER | 输出Token |
| latency_ms | INTEGER | 延迟ms |
| status | VARCHAR(20) | 状态 |
| created_at | TIMESTAMP | 创建时间 |

---

## 五、接口设计

### 5.1 对话接口

```http
POST /api/v1/chat
Content-Type: application/json
Authorization: Bearer <token>

{
  "session_id": "sess_123",
  "message": "本月新增客户有哪些？",
  "context": {}
}

Response (流式SSE):
event: intent
data: {"intent": "data_query", "confidence": 0.95}

event: sql
data: {"sql": "SELECT * FROM customer WHERE created_at >= '2026-03-01'"}

event: result
data: {"columns": ["name", "phone", "created_at"], "rows": [...]}

event: ui_spec
data: {"type": "Table", "props": {...}}

event: done
data: {}
```

### 5.2 待办聚合接口

```http
GET /api/v1/tasks/aggregate
Authorization: Bearer <token>

Response:
{
  "code": 200,
  "data": {
    "total_count": 10,
    "tasks": [
      {
        "id": "task_001",
        "title": "审批采购单",
        "source_system": "ERP",
        "status": "pending",
        "deadline": "2026-03-20T18:00:00Z",
        "external_url": "https://erp.example.com/task/123"
      }
    ],
    "source_stats": {
      "ERP": 3,
      "CRM": 5,
      "OA": 2
    }
  }
}
```

### 5.3 知识检索接口

```http
POST /api/v1/knowledge/search
Content-Type: application/json
Authorization: Bearer <token>

{
  "query": "年假政策",
  "top_k": 5,
  "category": "policy"
}

Response:
{
  "code": 200,
  "data": {
    "results": [
      {
        "id": "doc_001",
        "title": "员工年假管理办法",
        "content": "第一章 总则\n第一条 为了保障员工休息权利...",
        "score": 0.92,
        "chunk_id": "chunk_001"
      }
    ]
  }
}
```

### 5.4 数据查询接口

```http
POST /api/v1/query/text2sql
Content-Type: application/json
Authorization: Bearer <token>

{
  "question": "本月新增客户有哪些？"
}

Response:
{
  "code": 200,
  "data": {
    "sql": "SELECT name, phone, created_at FROM customer WHERE created_at >= '2026-03-01'",
    "columns": ["name", "phone", "created_at"],
    "rows": [
      ["张三", "13800138000", "2026-03-01"],
      ["李四", "13900139000", "2026-03-05"]
    ],
    "row_count": 2,
    "execution_time_ms": 123
  }
}
```

### 5.5 动态UI渲染接口

```http
POST /api/v1/ui/generate
Content-Type: application/json
Authorization: Bearer <token>

{
  "intent": "data_query",
  "data": {
    "type": "customer_list",
    "result": [...]
  }
}

Response:
{
  "code": 200,
  "data": {
    "type": "Table",
    "props": {
      "columns": ["客户名称", "手机号", "创建时间"],
      "data": [["张三", "138****", "2026-03-01"]],
      "title": "客户列表"
    }
  }
}
```

---

## 六、实施计划

### 6.1 Sprint规划

| Sprint | 时间 | 目标 | 交付物 |
|--------|------|------|--------|
| Sprint 0 | 第1周 | 环境搭建 | 开发环境就绪，代码仓库初始化 |
| Sprint 1 | 第2-3周 | 核心框架 | AI网关框架，意图分类MVP |
| Sprint 2 | 第4-5周 | 对话能力 | assistant-ui集成，基础对话 |
| Sprint 3 | 第6-7周 | 知识问答 | RAG Pipeline，Milvus集成 |
| Sprint 4 | 第8-9周 | 数据查询 | Vanna.ai集成，Text2SQL |
| Sprint 5 | 第10-11周 | 动态UI | json-render集成，UI生成 |
| Sprint 6 | 第12周 | 系统集成 | ERP/CRM/OA适配器 |
| Sprint 7 | 第13-14周 | 优化测试 | 性能优化，Bug修复 |
| Sprint 8 | 第15-16周 | 验收上线 | UAT，灰度发布 |

### 6.2 Sprint详细任务

#### Sprint 0: 环境搭建（第1周）

| 任务 | 负责人 | 验收标准 |
|------|--------|----------|
| 代码仓库初始化 | 前端+后端 | Git仓库创建完成 |
| Docker Compose环境 | 后端 | MySQL/Redis/Milvus可运行 |
| 前端项目初始化 | 前端 | React + Vite项目创建 |
| Python AI服务模板 | 后端 | FastAPI项目创建 |
| 开发规范文档 | 架构师 | 代码规范、Git流程 |

#### Sprint 1: 核心框架（第2-3周）

| 任务 | 负责人 | 验收标准 |
|------|--------|----------|
| AI网关核心架构 | 后端 | 路由、鉴权基础能力 |
| 意图分类模型部署 | 算法 | Qwen2.5-7B本地部署 |
| 意图分类服务开发 | 后端 | 4类意图分类准确率>85% |
| 前端页面框架搭建 | 前端 | 页面布局、路由配置 |
| assistant-ui集成 | 前端 | 对话界面可运行 |

#### Sprint 2: 对话能力（第4-5周）

| 任务 | 负责人 | 验收标准 |
|------|--------|----------|
| 流式输出支持 | 前端+后端 | SSE流式输出 |
| 多轮对话能力 | 前端+后端 | 支持上下文记忆 |
| Markdown渲染 | 前端 | 支持代码高亮、表格 |
| 意图路由开发 | 后端 | 根据意图分发到不同服务 |

#### Sprint 3: 知识问答（第6-7周）

| 任务 | 负责人 | 验收标准 |
|------|--------|----------|
| Milvus部署 | 运维 | Milvus集群可访问 |
| 文档处理Pipeline | 后端 | PDF/Word解析、切分 |
| Embedding服务 | 后端 | BGE-M3模型集成 |
| RAG检索服务 | 后端 | 混合检索，召回率>80% |
| 知识库管理界面 | 前端 | 文档上传、查询 |

#### Sprint 4: 数据查询（第8-9周）

| 任务 | 负责人 | 验收标准 |
|------|--------|----------|
| Vanna.ai集成 | 后端 | Text2SQL可运行 |
| Schema训练 | 后端+算法 | 导入业务表结构 |
| 问答对训练 | 后端+算法 | 20+问答对训练 |
| 结果表格展示 | 前端 | json-render Table渲染 |
| SQL安全检查 | 后端 | 防止SQL注入 |

#### Sprint 5: 动态UI（第10-11周）

| 任务 | 负责人 | 验收标准 |
|------|--------|----------|
| json-render集成 | 前端 | 组件目录定义完成 |
| UI Spec生成服务 | 后端 | LLM生成JSON Spec |
| 多种组件渲染 | 前端 | Table/Card/List/Metric |
| 流式UI渲染 | 前端 | 支持流式更新 |

#### Sprint 6: 系统集成（第12周）

| 任务 | 负责人 | 验收标准 |
|------|--------|----------|
| ERP Adapter开发 | 后端 | 金蝶/用友API对接 |
| CRM Adapter开发 | 后端 | 销售易等API对接 |
| OA Adapter开发 | 后端 | 泛微等API对接 |
| 待办聚合服务 | 后端 | 多系统待办聚合 |
| 跳转链接生成 | 后端 | 支持跳转原系统 |

#### Sprint 7: 优化测试（第13-14周）

| 任务 | 负责人 | 验收标准 |
|------|--------|----------|
| 性能优化 | 全员 | P99延迟<2s |
| Bug修复 | 全员 | 无阻塞性Bug |
| 安全加固 | 安全 | 渗透测试通过 |
| 监控告警 | 运维 | Prometheus+Grafana |
| 日志系统 | 运维 | ELK日志收集 |

#### Sprint 8: 验收上线（第15-16周）

| 任务 | 负责人 | 验收标准 |
|------|--------|----------|
| UAT测试 | 测试+业务 | 功能验收通过 |
| 灰度发布 | 运维 | 10%流量灰度 |
| 全量发布 | 运维 | 正式上线 |
| 文档交付 | 全员 | 操作手册、API文档 |

---

## 七、验收标准

### 7.1 功能验收标准

| 功能 | 验收条件 | 测试方法 |
|------|----------|----------|
| F1 统一工作台 | 能显示所有来源待办 | 导入测试账号，查看待办列表 |
| F2 AI对话 | 能进行多轮对话 | 执行5轮对话测试 |
| F3 知识问答 | 回答准确率>85% | 20道测试题抽检 |
| F4 数据查询 | SQL准确率>85% | 20道查询题抽检 |
| F5 动态UI | 能渲染Table/List/Card | 多种数据类型测试 |

### 7.2 性能验收标准

| 指标 | 目标值 | 测试方法 |
|------|--------|----------|
| 意图分类延迟 | <200ms | 100次测试取P99 |
| RAG检索延迟 | <500ms | 100次测试取P99 |
| Text2SQL延迟 | <3s | 100次测试取P99 |
| UI渲染时间 | <100ms | 100次测试取P99 |
| 系统可用性 | >=99.9% | 7x24监控 |

### 7.3 安全验收标准

| 检查项 | 标准 |
|--------|------|
| SQL注入 | 无法注入恶意SQL |
| XSS攻击 | 无法注入恶意脚本 |
| 敏感信息 | 手机号、身份证脱敏 |
| 日志审计 | 全部操作有日志 |

---

## 附录A：MVP技术栈清单

| 组件 | 选型 | 说明 |
|------|------|------|
| 前端框架 | React 18 + Vite | |
| AI对话 | assistant-ui 0.12+ | YC支持，专业AI对话 |
| 动态UI | json-render | Vercel Labs出品 |
| UI组件 | Ant Design 5.x | |
| 状态管理 | Zustand | |
| 后端框架 | Spring Boot 3.x | |
| AI网关 | FastAPI | Python异步框架 |
| 本地LLM | Qwen2.5 + Ollama | 意图分类 |
| RAG | LangChain + Milvus | |
| Text2SQL | Vanna.ai 2.0 | |
| 向量数据库 | Milvus 2.3+ | |
| 缓存 | Redis 7.x | |
| 消息队列 | RabbitMQ 3.12 | |
| 数据库 | PostgreSQL 15+ | |
| 日志分析 | ClickHouse | |
| 部署 | Docker Compose | 开发/测试 |

---

## 附录B：风险与应对

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| LLM效果不达预期 | 高 | 中 | 多模型备选，人工兜底 |
| 系统对接困难 | 高 | 中 | 提前评估API能力 |
| 性能不达标 | 中 | 低 | 提前做性能测试 |
| 用户采纳率低 | 中 | 中 | 充分培训，激励机制 |

---

> **文档版本**：V1.0
> **编制时间**：2026年3月19日
> **下次评审时间**：2026年4月1日
