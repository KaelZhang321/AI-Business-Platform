# ROADMAP

## Phase 01: ai-gateway Meeting BI Integration

### Goal

让 `ai-gateway` 在不破坏现有通用问数链路的前提下，接入会议 BI 专用问数执行器与固定 BI 看板接口。

### Acceptance Criteria

- `Text2SQLService` 仍是统一问数入口
- 命中会议 BI 语义时，可自动分流到 `MeetingBIQueryExecutor`
- Direct API / MCP 可通过显式 `domain=meeting_bi` 走 BI 执行器
- 固定 BI 看板接口挂载到 `/api/v1/bi/*`
- 通用问数与会议 BI 使用独立配置和数据连接
- 自动化验证覆盖问数分流和 BI 路由

### Execution Waves

- Wave 1: 查询契约/分类基础、BI 域脚手架
- Wave 2: 通用问数门面重构、固定 BI 看板接口
- Wave 3: 会议 BI 问数执行器集成
- Wave 4: 自动化验证与回归收口
