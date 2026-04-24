# 优化方案11：GraphRAG融合方案

> 解决问题：RAG（P0）和知识图谱（P2优先级）各自规划，未设计融合架构
> 优先级：P2（中优先级，Q2-Q3设计，配合P8 v2.0实施）
> 工作量：2天设计 + 持续迭代
> 影响范围：P8知识库平台（M2）、全产品AI检索质量

---

## 一、问题分析

### 1.1 当前RAG与知识图谱的割裂状态

```
当前架构（割裂）：

  路径A：向量检索（RAG）
  用户问题 → Embedding → Milvus相似度搜索 → Top-K Chunks → LLM生成
  优势：语义理解强，泛化能力好
  不足：缺乏实体关系推理，多跳问题弱

  路径B：知识图谱查询（P2优先级，规划中）
  用户问题 → 实体识别 → 图谱查询 → 关系路径 → 结构化答案
  优势：关系推理精确，可解释性强
  不足：覆盖面受限于图谱构建质量
```

### 1.2 融合的必要性

| 问题类型 | 仅RAG | 仅图谱 | GraphRAG融合 |
|---------|-------|--------|-------------|
| "高血压的常见症状有哪些？" | ✅ 语义检索 | ⚠️ 需建好实体 | ✅ |
| "张三目前在用什么药？" | ⚠️ 可能检索多个患者 | ✅ 精确查询 | ✅ |
| "阿司匹林和华法林能一起吃吗？" | ⚠️ 可能遗漏 | ✅ 关系推理 | ✅ |
| "糖尿病合并高血压应该用什么方案？" | ⚠️ 单一文档 | ⚠️ 多跳推理复杂 | ✅ 融合推理 |
| "类似张三情况的患者通常怎么治疗？" | ❌ 缺乏关联 | ⚠️ 需案例图谱 | ✅ |

---

## 二、GraphRAG融合架构

### 2.1 总体架构

```
┌──────────────────────────────────────────────────┐
│                GraphRAG 融合检索引擎               │
│                                                   │
│  用户问题                                          │
│      │                                            │
│      ▼                                            │
│  ┌──────────────────┐                             │
│  │  意图分析 + 实体识别 │                           │
│  │  (LLM / NER模型)   │                           │
│  └────────┬─────────┘                             │
│           │                                        │
│     ┌─────┼─────┐                                  │
│     │     │     │                                  │
│     ▼     ▼     ▼                                  │
│  ┌─────┐ ┌─────┐ ┌──────────┐                     │
│  │向量  │ │关键词│ │ 图谱查询  │                     │
│  │检索  │ │检索  │ │          │                     │
│  │Milvus│ │ES   │ │ Neo4j    │                     │
│  │Top-20│ │Top-20│ │ Cypher   │                     │
│  └──┬──┘ └──┬──┘ └────┬─────┘                     │
│     │       │          │                            │
│     └───────┼──────────┘                            │
│             ▼                                       │
│  ┌──────────────────────┐                          │
│  │    融合排序器           │                          │
│  │  (RRF + 图谱增强)      │                          │
│  │                        │                          │
│  │  向量结果 ×0.4          │                          │
│  │  关键词结果 ×0.3        │                          │
│  │  图谱结果 ×0.3          │                          │
│  │  → 重排序(BGE-Reranker) │                         │
│  └──────────┬───────────┘                          │
│             ▼                                       │
│  ┌──────────────────────┐                          │
│  │  上下文组装             │                          │
│  │  RAG Chunks            │                          │
│  │  + 图谱实体关系         │                          │
│  │  + 图谱路径解释         │                          │
│  └──────────┬───────────┘                          │
│             ▼                                       │
│  ┌──────────────────────┐                          │
│  │  LLM生成（带来源标注）  │                          │
│  │  DeepSeek V3           │                          │
│  └──────────────────────┘                          │
└──────────────────────────────────────────────────┘
```

### 2.2 医疗知识图谱Schema

```
┌──────────────────────────────────────────────┐
│           医疗知识图谱实体关系模型              │
│                                               │
│  核心实体：                                    │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐     │
│  │ 疾病  │  │ 药物  │  │ 症状  │  │ 检查  │     │
│  │Disease│  │Drug  │  │Symptom│  │Test  │     │
│  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘     │
│     │         │         │         │          │
│  核心关系：                                    │
│  疾病 ─[表现为]→ 症状                          │
│  疾病 ─[治疗用药]→ 药物                        │
│  疾病 ─[确诊检查]→ 检查                        │
│  药物 ─[禁忌联用]→ 药物    (配伍禁忌)           │
│  药物 ─[适应症]→ 疾病                          │
│  药物 ─[不良反应]→ 症状                        │
│  药物 ─[禁忌人群]→ 人群特征                     │
│                                               │
│  业务实体：                                    │
│  ┌──────┐  ┌──────┐  ┌──────┐               │
│  │ 患者  │  │ 方案  │  │ 服务  │               │
│  │Patient│  │Plan  │  │Service│              │
│  └──┬───┘  └──┬───┘  └──┬───┘               │
│     │         │         │                     │
│  患者 ─[诊断为]→ 疾病                          │
│  患者 ─[正在服用]→ 药物                        │
│  患者 ─[执行方案]→ 方案                        │
│  方案 ─[包含服务]→ 服务                        │
│  方案 ─[治疗目标]→ 疾病                        │
└──────────────────────────────────────────────┘
```

### 2.3 Neo4j图谱存储选型

| 维度 | Neo4j Community | NebulaGraph | PostgreSQL + AGE |
|------|----------------|-------------|-----------------|
| 图查询语言 | Cypher（最成熟） | nGQL | Cypher（兼容） |
| 社区生态 | 最大 | 中等 | 小 |
| 部署复杂度 | 低（单节点） | 高（分布式） | 低（PG扩展） |
| 数据规模 | 百万节点 | 亿级节点 | 百万节点 |
| 与现有技术栈兼容 | Java Driver成熟 | — | 需额外引入PostgreSQL |
| 许可证 | GPL（Community免费） | Apache 2.0 | Apache 2.0 |

**推荐：Neo4j Community Edition**
- 医疗知识图谱规模在百万节点内，Neo4j完全满足
- Cypher查询语言最成熟，社区资源最丰富
- Spring Data Neo4j可直接集成
- 后期如需分布式扩展，可迁移到NebulaGraph

---

## 三、融合检索流程详细设计

### 3.1 意图分析 + 实体识别

```python
# 意图分类 + 实体抽取（LLM方式）
async def analyze_query(query: str) -> QueryAnalysis:
    prompt = """分析以下医疗问题，提取：
    1. 查询意图：FACTUAL(事实查询) / RELATIONAL(关系查询) / REASONING(推理查询)
    2. 实体列表：疾病、药物、症状、检查、患者等
    3. 关系类型：治疗、禁忌、症状、检查等

    问题：{query}

    输出JSON格式：
    {{"intent": "...", "entities": [...], "relations": [...]}}
    """

    result = await llm.generate(prompt.format(query=query))
    return QueryAnalysis.parse(result)
```

### 3.2 三路检索并行执行

```python
async def graphrag_search(query: str, kb_id: str) -> SearchResults:
    # 1. 意图分析
    analysis = await analyze_query(query)

    # 2. 三路并行检索
    vector_task = vector_search(query, kb_id, top_k=20)
    keyword_task = keyword_search(query, kb_id, top_k=20)
    graph_task = graph_search(analysis.entities, analysis.relations)

    vector_results, keyword_results, graph_results = await asyncio.gather(
        vector_task, keyword_task, graph_task
    )

    # 3. 融合排序
    fused = fusion_rank(
        vector_results,    # 权重 0.4
        keyword_results,   # 权重 0.3
        graph_results,     # 权重 0.3
        intent=analysis.intent
    )

    # 4. 重排序
    reranked = await reranker.rerank(query, fused, top_k=8)

    return reranked
```

### 3.3 图谱查询策略

```python
async def graph_search(entities: list, relations: list) -> list:
    results = []

    for entity in entities:
        # 单跳查询：直接关系
        cypher_1hop = """
        MATCH (n)-[r]->(m)
        WHERE n.name = $name
        RETURN n, type(r) as relation, m
        LIMIT 20
        """

        # 双跳查询：间接关系（如：药物→禁忌→另一药物→适应症→疾病）
        cypher_2hop = """
        MATCH path = (n)-[*1..2]->(m)
        WHERE n.name = $name
        RETURN path
        LIMIT 10
        """

        if analysis.intent == "RELATIONAL":
            results.extend(neo4j.query(cypher_2hop, name=entity.name))
        else:
            results.extend(neo4j.query(cypher_1hop, name=entity.name))

    return results
```

### 3.4 RRF融合排序算法

```python
def fusion_rank(vector_results, keyword_results, graph_results,
                intent: str) -> list:
    """
    Reciprocal Rank Fusion (RRF) + 意图自适应权重
    """
    # 意图自适应权重
    weights = {
        "FACTUAL":    {"vector": 0.5, "keyword": 0.3, "graph": 0.2},
        "RELATIONAL": {"vector": 0.2, "keyword": 0.2, "graph": 0.6},
        "REASONING":  {"vector": 0.35, "keyword": 0.25, "graph": 0.4},
    }
    w = weights.get(intent, weights["FACTUAL"])

    # RRF评分
    k = 60  # RRF常数
    scores = {}

    for rank, doc in enumerate(vector_results):
        scores[doc.id] = scores.get(doc.id, 0) + w["vector"] / (k + rank + 1)

    for rank, doc in enumerate(keyword_results):
        scores[doc.id] = scores.get(doc.id, 0) + w["keyword"] / (k + rank + 1)

    for rank, doc in enumerate(graph_results):
        doc_id = f"graph_{doc.entity_id}"
        scores[doc_id] = scores.get(doc_id, 0) + w["graph"] / (k + rank + 1)

    # 按融合分数降序
    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results[:30]  # 送入Reranker的候选集
```

---

## 四、上下文组装策略

### 4.1 Prompt模板

```python
GRAPHRAG_PROMPT = """基于以下检索结果回答问题。

## 文档检索结果（RAG）
{rag_chunks}

## 知识图谱关系
{graph_context}

## 用户问题
{query}

## 回答要求
1. 综合文档和图谱信息回答
2. 标注信息来源（[文档:xxx] 或 [图谱:实体→关系→实体]）
3. 如果存在药物相互作用风险，必须醒目提示
4. 不确定的信息标注置信度
"""

def assemble_context(rag_results, graph_results):
    # RAG chunks格式化
    rag_chunks = "\n".join([
        f"[来源:{r.doc_name}, 相关度:{r.score:.2f}]\n{r.content}"
        for r in rag_results
    ])

    # 图谱关系格式化
    graph_lines = []
    for g in graph_results:
        graph_lines.append(
            f"- {g.source.name}({g.source.type}) "
            f"─[{g.relation}]→ "
            f"{g.target.name}({g.target.type})"
        )
    graph_context = "\n".join(graph_lines)

    return GRAPHRAG_PROMPT.format(
        rag_chunks=rag_chunks,
        graph_context=graph_context,
        query=query
    )
```

---

## 五、图谱构建Pipeline

### 5.1 自动图谱构建流程

```
┌──────────────────────────────────────────────┐
│           知识图谱自动构建Pipeline              │
│                                               │
│  医疗文档/指南/药品说明书                       │
│       │                                       │
│       ▼                                       │
│  ① 文档解析（与RAG共用）                       │
│       │                                       │
│       ▼                                       │
│  ② NER实体识别（LLM + 医疗NER模型）            │
│     → 疾病、药物、症状、检查 实体               │
│       │                                       │
│       ▼                                       │
│  ③ 关系抽取（LLM）                             │
│     → 治疗、禁忌、症状表现、检查确诊 关系       │
│       │                                       │
│       ▼                                       │
│  ④ 实体对齐 + 去重（同义词/别名合并）           │
│     → "高血压" = "高血压病" = "原发性高血压"    │
│       │                                       │
│       ▼                                       │
│  ⑤ 质量校验（人工抽检 + 自动一致性检查）        │
│       │                                       │
│       ▼                                       │
│  ⑥ 入库Neo4j                                  │
└──────────────────────────────────────────────┘
```

### 5.2 图谱规模估算

| 实体类型 | 预估数量 | 来源 |
|---------|---------|------|
| 疾病 | ~5,000 | ICD-10编码 |
| 药物 | ~8,000 | 药品目录 |
| 症状 | ~3,000 | 症状词典 |
| 检查 | ~2,000 | 检查项目库 |
| 健康服务 | ~500 | 丽滋卡尔服务目录 |
| **总实体** | **~18,500** | |
| **总关系** | **~50,000-100,000** | 实体间关系 |

**存储估算**：Neo4j Community单节点，<1GB存储，完全满足。

---

## 六、版本规划

| P8版本 | GraphRAG能力 | 交付物 |
|--------|-------------|--------|
| v0.5 | 仅RAG向量检索 | 混合检索（Milvus+ES）|
| v1.0 | RAG + 基础图谱 | Neo4j部署 + 药物实体图谱（配伍禁忌） |
| v1.5 | 二路融合（RAG+图谱） | 融合排序器 + 图谱查询集成 |
| v2.0 | 三路融合（完整GraphRAG） | 意图自适应权重 + 上下文组装优化 |
| v2.5 | 图谱自动扩充 | 自动实体关系抽取Pipeline |

---

## 七、执行检查清单

- [ ] Neo4j Community Docker部署
- [ ] 设计医疗知识图谱Schema（实体+关系）
- [ ] 导入药品配伍禁忌基础图谱（优先，配合补充方案06）
- [ ] 开发NER实体识别服务（LLM+规则混合）
- [ ] 开发三路并行检索框架
- [ ] 实现RRF融合排序（意图自适应权重）
- [ ] 设计GraphRAG Prompt模板
- [ ] A/B测试：纯RAG vs GraphRAG检索质量对比
- [ ] 图谱质量评估：实体识别F1≥85%，关系准确率≥80%
