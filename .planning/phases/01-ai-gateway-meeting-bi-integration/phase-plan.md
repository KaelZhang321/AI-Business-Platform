# Phase Plan: ai-gateway Meeting BI Integration

## Goal

在 `ai-gateway` 内完成会议 BI 第一阶段融合，使统一问数入口能够按意图切换到会议 BI 执行器，并提供固定 BI 看板接口。

## Phase Directory

- `.planning/phases/01-ai-gateway-meeting-bi-integration/`

## Execution Order

### Wave 1

- `01-01-PLAN.md` 查询契约、分类与配置基础
- `01-02-PLAN.md` BI 域脚手架与共享数据访问层

### Wave 2

- `01-03-PLAN.md` 通用问数门面重构
- `01-05-PLAN.md` 固定 BI 看板接口迁入

### Wave 3

- `01-04-PLAN.md` 会议 BI 问数执行器接入

### Wave 4

- `01-06-PLAN.md` 自动化验证与回归收口

## Dependency Graph

- `01-01` -> `01-03`, `01-04`
- `01-02` -> `01-04`, `01-05`
- `01-03` -> `01-04`, `01-06`
- `01-05` -> `01-06`
- `01-04` -> `01-06`

## Acceptance Criteria

- 统一问数入口继续由 `Text2SQLService` 提供
- 会议 BI 语义通过 `data_meeting_bi` 二级意图或显式 `domain=meeting_bi` 进入 BI 执行器
- 固定 BI 看板接口挂载到 `/api/v1/bi/*`
- 通用问数与会议 BI 配置、连接、训练数据隔离
- 存在自动化验证覆盖问数分流和 BI 路由

## Non-Goals

- 企业微信长连接
- Webhook 推送
- 状态控制接口
- 通过 `business-server` 转发 BI 数据
