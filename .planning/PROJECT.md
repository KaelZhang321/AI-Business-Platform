# PROJECT

## Project

将 `ai-bi-new` 的会议 BI 后端能力融合进 `AI-Business-Platform/ai-gateway`，形成统一问数入口、独立 BI 域模块和统一部署形态。

## Current Goal

完成 `ai-gateway` 会议 BI 集成第一阶段的可执行实现计划，覆盖：

- 固定 BI 看板接口迁入
- 会议 BI 问数能力迁入
- 通用问数入口内部对会议 BI 意图分流

## Boundaries

- 第一阶段保留直连会议 BI MySQL 与 `meeting_*` 表
- 不通过 `business-server` 转发取数
- 不迁企业微信长连接、Webhook 推送、状态控制接口
- 统一问数入口继续使用 `Text2SQLService`

## Source of Truth

- 设计文档：`docs/plans/2026-03-28-ai-gateway-meeting-bi-integration-design.md`

## Success Definition

- `ai-gateway` 可以通过统一问数入口处理会议 BI 查询
- `ai-gateway` 暴露固定 BI 看板接口 `/api/v1/bi/*`
- 会议 BI 数据源、训练语料、执行器与通用问数隔离
- 存在可执行的 GSD phase plans，可直接进入 `/gsd:execute-phase`
