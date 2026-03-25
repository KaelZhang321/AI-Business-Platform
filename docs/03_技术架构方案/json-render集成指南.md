# json-render 集成指南

## 概述

本项目使用 `@json-render/react` 0.14 实现动态 UI 渲染，AI 网关返回 JSON Spec，前端通过 `createRenderer` + Ant Design 组件混合渲染。

## 架构流程

```
AI网关(Python)                    前端(React)
┌─────────────────┐              ┌──────────────────────┐
│ DynamicUIService │──JSON Spec──→│ DynamicRenderer.tsx   │
│  - 规则模式      │   via SSE    │  - createRenderer()   │
│  - LLM模式(实验) │              │  - Ant Design 组件    │
└─────────────────┘              └──────────────────────┘
```

## 支持的 7 种组件

| 组件 | 用途 | 数据来源 |
|------|------|----------|
| Card | 容器卡片 | 所有意图 |
| Table | 数据表格 | Text2SQL 查询结果 |
| Metric | 指标数字 | 数值聚合(sum/avg/count) |
| List | 列表展示 | 知识检索/任务列表 |
| Form | 表单筛选 | 任务筛选条件 |
| Tag | 标签 | 状态/分类标记 |
| Chart | ECharts 图表 | bar/line/pie 自动选择 |

## 后端 Spec 生成

文件：`ai-gateway/app/services/dynamic_ui_service.py`

```python
# 入口方法
async def generate_ui_spec(self, intent: str, data: Any, context: dict | None = None) -> dict | None
```

三种意图对应的生成逻辑：
- `knowledge` → Card > List（知识检索结果）
- `query` → Card > Metric + Chart + Table（SQL查询结果）
- `task` → Card > Form + List（任务列表+筛选）

图表类型自动检测：`_detect_chart_type()` 根据类别数量和时间特征选择 pie/line/bar。

LLM 模式（实验性）：设置 `LLM_UI_SPEC_ENABLED=true` 启用，LLM 生成失败时自动回退规则模式。

## 前端渲染

文件：`frontend/src/components/dynamic-ui/DynamicRenderer.tsx`

```typescript
// 组件注册
const JsonRenderUI = createRenderer(catalog, { Card, Table, Metric, List, Form, Tag, Chart })

// 使用
<DynamicRenderer spec={uiSpec} onAction={handleAction} />
```

### catalog.ts

定义 Zod schema 验证每个组件的 props 结构，以及 `UIAction` 类型和 `normalizeSpec()` 规范化函数。

### Action 机制

通过 `ActionContext` (React Context) 传递 action handler：

| action.type | 触发场景 | 行为 |
|-------------|----------|------|
| trigger_task | Form 提交 | 发送创建任务请求 |
| view_detail | List 项点击 | 查询任务详情 |
| open_link | 外部链接 | window.open() |
| export | Table 导出 | CSV 导出 |
| refresh | 刷新按钮 | 重新请求 |

## SSE 事件流

AI 对话通过 SSE 流式传输 UI Spec：

```
event: intent
data: {"intent": "query", "sub_intent": "data_sales"}

event: content
data: {"text": "为您查询到以下数据："}

event: ui_spec
data: {"type": "Card", "props": {...}, "children": [...]}

event: sources
data: [{"sql": "SELECT ..."}]

event: done
data: {"conversation_id": "xxx"}
```

前端 `AIChat.tsx` 的 `handleRawEvent()` 解析 `ui_spec` 事件后调用 `setUiSpec(parsed)` 触发 DynamicRenderer 渲染。
