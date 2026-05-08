## AIComponentManagementView → JSON-Render 组件拆分计划（通用原子 + 少量复合）

### Summary
- 目标：将 `AIComponentManagementView.tsx` 中“业务展示组件”按 JSON-Render 可复用颗粒度拆分到 `catalog.ts` + `registry.tsx`，并同步一份可直接渲染的完整示例 spec。
- 已锁定决策：
- 颗粒度：通用原子 + 少量复合（不做 16 个一对一重复组件）。
- 范围：仅业务展示组件，不包含页面管理壳子（筛选条、布局编辑流程、弹窗流程）。
- 数据组织：结构化数组 props（sections/items/tiles/rows）。
- 交付：`catalog.ts` 与 `registry.tsx` 完整落地 + `spec.ts` 新增一个完整示例。

### Key Changes
- 在 `catalog.ts` 新增并标准化组件声明（保留并兼容现有 `Planner*` 名称体系）：
- `PlannerCard`：卡片容器（`title/subtitle/headerRightText`）。
- `PlannerInfoGrid`：信息网格（`items[]`，每项 `label/value`，支持列配置）。
- `PlannerSectionBlocks`：分区块容器（`sections[]`，每块 `title/icon/tone/items[]`）。
- `PlannerMetricTiles`：指标卡组（`tiles[]`，每项 `label/value/desc/icon/tone`）。
- `PlannerTable`：表格展示（沿用并对齐当前表格能力，支持 `columns/rows`）。
- `PlannerHighlightNote`：备注/提示块（`text/tone`）。
- `PlannerOwnerMeta`：负责人与执行日期块（`name/executionDate/lastUpdateDate`）。
- 保留并继续支持现有 `PlannerForm/PlannerInput/PlannerSelect/PlannerButton/PlannerNotice`（不破坏已存在 spec）。
- 在 `registry.tsx` 实现对应渲染器：
- 抽出统一样式 token（卡片外壳、标题栏、字段文本、区块色板），保证与 `AIComponentManagementView` 视觉一致。
- 组件以“数据驱动”渲染，不在 registry 写死业务字段。
- `PlannerSectionBlocks` 与 `PlannerMetricTiles` 负责覆盖原文件中高频“分色区块/指标块”样式。
- `PlannerTable` 映射教育铺垫记录表格样式（表头、行间距、暗色模式）。
- `PlannerOwnerMeta` 复刻负责人头像首字母 + 两列日期信息。
- 在 `spec.ts` 新增一个完整示例（不替换现有默认示例）：
- 示例覆盖：卡片容器 + 信息网格 + 分区块 + 指标卡 + 表格 + 备注 + 负责人区块。
- 示例使用结构化数组入参，演示“同一原子组件可复用于多个业务卡”。
- 兼容性策略：
- 采用“增量新增”而非“重命名替换”，确保现有 `res.json` / 历史 `Planner*` spec 不回归。
- 不改 `AssistantMessageContent` 的消费链路与 `onAction` 机制。

### 组件映射（AIComponentManagementView → JSON-Render）
- `AssetCard` → `PlannerCard + PlannerMetricTiles`
- `IdentityContactCard / HealthStatusMedicalHistoryCard / PhysicalExamStatusCard` → `PlannerCard + PlannerInfoGrid`
- `LifestyleHabitsCard / PsychologyEmotionCard / PersonalPreferencesCard / HealthGoalsCard / ConsumptionAbilityCard / CustomerRelationsCard / ConsultationRecordsCard` → `PlannerCard + PlannerSectionBlocks`
- `EducationRecordsCard` → `PlannerCard + PlannerTable`
- `RemarksCard` → `PlannerCard + PlannerHighlightNote`
- `ExecutionDateCard` → `PlannerCard + PlannerOwnerMeta`
- `PrecautionsCard` → v1 先用 `PlannerCard + PlannerInfoGrid`（展示态）；编辑态继续由现有表单原子承接

### Test Plan
- Schema 校验：
- 新增组件 props 在 `catalog.ts` Zod 校验通过（必填/可选/数组结构）。
- 旧 `Planner*` 示例与 `res.json` 不因新增组件失效。
- 渲染校验：
- 用新增完整示例 spec 渲染，逐项确认：标题区、网格字段、分区块、指标块、表格、备注块、负责人块。
- 深色/浅色模式视觉结构与间距保持一致。
- 交互与兼容：
- 现有 `PlannerForm/Input/Button/Select` 行为不变（`$bindState`、`emit('press')`、`onAction`）。
- 不引入对页面壳子状态的耦合（组件独立可复用）。

### Assumptions
- 本次只改 `catalog.ts`、`registry.tsx`、`spec.ts`；不改 `AIComponentManagementView.tsx` 页面逻辑。
- 业务数据由 spec 直接下发（结构化数组）；registry 不内置业务 mock。
- 旧组件名称与旧 spec 保持可用，新增能力以扩展方式提供。
- 图标采用字符串键映射（在 registry 内做安全映射），避免在 spec 中直接传 React 组件实例。
