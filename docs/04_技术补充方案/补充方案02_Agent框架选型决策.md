# 补充方案02：Agent编排框架选型决策

> 解决问题：三份文档提及三种不同Agent框架，需最终选型
> 优先级：P0（0.5天工作量）
> 决策影响：P8 M5智能体平台、全产品AI能力调用

---

## 一、候选框架对比

### 1.1 三个候选方案

| 维度 | LangChain | LangGraph | AutoGen |
|------|-----------|-----------|---------|
| **核心范式** | 链式编排（Chain/Pipeline） | 有限状态机（Graph+State） | 多Agent对话（Multi-Agent） |
| **适用场景** | RAG/Tool Calling/简单链 | 复杂流程控制/条件分支/循环 | 多角色协作/辩论式推理 |
| **状态管理** | 无内置（需手动） | 内置Checkpoint/State | 内置会话历史 |
| **Python生态** | 最成熟，插件最多 | LangChain团队维护，兼容LangChain | 微软开发，独立生态 |
| **Java生态** | LangChain4J（社区维护） | 无Java版本 | 无Java版本 |
| **Spring集成** | LangChain4J + Spring AI | 无 | 无 |
| **学习曲线** | 低 | 中 | 中高 |
| **社区活跃度** | 最高（GitHub 100K+ stars） | 高（快速增长） | 中（微软主导） |
| **生产就绪度** | 高 | 中高 | 中 |
| **监控/追踪** | LangSmith（官方） | LangSmith（兼容） | 自带日志 |

### 1.2 项目实际需求分析

| 需求场景 | 版本 | 复杂度 | 最适框架 |
|---------|------|--------|---------|
| RAG知识库检索 | P8 v0.5 | 低 | LangChain |
| AI对话/Copilot | P8 v0.5 | 低 | LangChain |
| 意图分类+路由 | P8 v0.5 | 低 | LangChain |
| 工作流编排（可视化） | P8 v1.5 | 中 | LangGraph |
| Function Calling | P8 v2.0 | 中 | LangChain + Tools |
| 单Agent执行 | P8 v2.0 | 中 | LangGraph |
| 多Agent协作 | P8 v2.5 | 高 | LangGraph（v2.5再评估AutoGen） |
| Java业务编排 | 全版本 | 中 | Spring AI / LangChain4J |

---

## 二、最终选型决策

### 2.1 选型结论

```
                    ┌─────────────────────────────────────┐
                    │          最终技术选型方案             │
                    ├─────────────────────────────────────┤
                    │                                     │
                    │  Python层（AI网关/AI服务）：           │
                    │    ✅ LangChain 0.3+（基础编排+RAG）   │
                    │    ✅ LangGraph 0.2+（Agent+工作流）   │
                    │    ❌ AutoGen（暂不引入，v2.5再评估）   │
                    │                                     │
                    │  Java层（业务编排）：                   │
                    │    ✅ Spring AI 1.0+（Spring原生集成）  │
                    │    ⚠️ LangChain4J（备选，按需引入）    │
                    │                                     │
                    │  监控追踪：                           │
                    │    ✅ LangSmith（Python层统一追踪）     │
                    │    ✅ SkyWalking（Java层链路追踪）      │
                    │                                     │
                    └─────────────────────────────────────┘
```

### 2.2 选型理由

**Python层选择 LangChain + LangGraph：**
1. LangChain是RAG/Tool Calling的事实标准，插件生态最丰富
2. LangGraph是LangChain团队出品，API完全兼容，无迁移成本
3. LangGraph的状态机模型适合P8 v1.5+的复杂工作流
4. LangSmith提供统一的追踪/调试/评估能力

**Java层选择 Spring AI：**
1. Spring官方项目，与Spring Boot 3.x深度集成
2. 支持多模型Provider（OpenAI/Anthropic/自定义）
3. 内置向量数据库抽象、RAG模板
4. 团队已用Spring Boot 3.x，学习成本最低

**不选AutoGen的原因：**
1. 多Agent协作场景（P8 v2.5）距今9个月，需求不紧急
2. AutoGen独立生态，与LangChain不兼容
3. 微软主导，API稳定性不如LangChain
4. v2.5时可作为补充评估，但不作为基础框架

### 2.3 各版本框架使用规划

| P8版本 | Python框架 | Java框架 | 核心能力 |
|--------|-----------|---------|---------|
| v0.5 | LangChain（RAG+Chain） | Spring AI（模型调用） | 知识库检索、AI对话 |
| v1.0 | LangChain（Tools+Router） | Spring AI（路由+权限） | 模型路由、API Key |
| v1.5 | LangGraph（StatefulGraph） | Spring AI + Flowable | 可视化工作流编排 |
| v2.0 | LangGraph（Agent） | Spring AI（Function Calling） | 单Agent+多模态+ASR |
| v2.5 | LangGraph（Multi-Agent） | Spring AI | 多Agent协作，评估是否引入AutoGen |
| v3.0 | 稳定化 | 稳定化 | 性能优化、安全加固 |

---

## 三、架构分层图

```
┌──────────────────────────────────────────────────┐
│                  前端应用层                        │
│    React 18 (P1-P5/P7/P8) | Vue 3 (P6)          │
│    assistant-ui | json-render | SSE              │
├──────────────────────────────────────────────────┤
│              Java业务编排层                        │
│    Spring Boot 3.x + Spring AI 1.0               │
│    Spring Cloud Gateway + Nacos + Flowable        │
│    业务逻辑 / 权限控制 / 数据访问                   │
├──────────────────────────────────────────────────┤
│              Python AI网关层                       │
│    FastAPI + LangChain 0.3 + LangGraph 0.2       │
│    ┌────────────────────────────────────────┐     │
│    │ v0.5: Chain(RAG) + Tools(Search/DB)    │     │
│    │ v1.5: StateGraph(Workflow)              │     │
│    │ v2.0: Agent(Function Calling)          │     │
│    │ v2.5: Multi-Agent(Supervisor Pattern)  │     │
│    └────────────────────────────────────────┘     │
│    IntentClassifier + RAG Engine + Vanna.ai       │
├──────────────────────────────────────────────────┤
│              模型与数据层                          │
│    DeepSeek V3 / Qwen-Max / WiNGPT / YiduCore   │
│    Milvus + MySQL + Redis + ES + ClickHouse      │
└──────────────────────────────────────────────────┘
```

---

## 四、执行检查清单

- [ ] 更新P8 PRD中Agent框架选型章节
- [ ] 更新设计方案/总体架构中的Agent框架描述（删除AutoGen）
- [ ] 更新业务中台架构文档中的AI框架章节
- [ ] pip安装清单确认：langchain==0.3.x, langgraph==0.2.x, langsmith
- [ ] Maven依赖确认：spring-ai-starter 1.0.x
- [ ] v2.5 Sprint规划中增加"AutoGen评估"任务
