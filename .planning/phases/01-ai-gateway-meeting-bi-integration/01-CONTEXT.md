# 01 CONTEXT

## Design Basis

- `docs/plans/2026-03-28-ai-gateway-meeting-bi-integration-design.md`

## Current Entry Points

- HTTP query route: `ai-gateway/app/api/routes/query.py`
- Chat orchestration: `ai-gateway/app/services/chat_workflow.py`
- Text2SQL facade candidate: `ai-gateway/app/services/text2sql_service.py`
- MCP tool surface: `ai-gateway/app/mcp_server/tools.py`
- Shared schemas: `ai-gateway/app/models/schemas.py`
- Intent routing: `ai-gateway/app/services/intent_classifier.py`
- Runtime config: `ai-gateway/app/core/config.py`

## Current Gaps

- 通用问数与会议 BI 问数尚未分流
- `database` 参数未实现多库切换
- 尚无 BI 域目录与独立数据连接
- 尚无 `/api/v1/bi/*` 固定看板接口
- 尚无自动化测试覆盖问数域分流

## Phase Constraints

- 第一阶段仅迁固定 BI 接口与 BI AI 查询
- 企业微信相关内容不进入本 phase
- Chat 自动分流，Direct API / MCP 显式分流
- 保留 `Text2SQLService` 作为统一入口，不旁路
