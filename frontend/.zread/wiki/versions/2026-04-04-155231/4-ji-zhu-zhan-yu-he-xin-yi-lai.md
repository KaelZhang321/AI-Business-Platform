本文档系统梳理 AI Business Platform 前端项目的技术选型与依赖架构。项目采用现代化的 React 生态系统，围绕类型安全、开发体验与生产性能三大核心目标构建，通过精细化的工具链配置实现从开发到部署的全流程工程化支撑。

## 核心框架与构建系统

项目基于 **React 19** 与 **TypeScript 5.8** 构建，采用 Vite 6 作为下一代构建工具。Vite 的原生 ESM 开发服务器提供毫秒级热更新响应，而其基于 Rollup 的生产构建通过智能代码分割策略确保首屏加载性能。TypeScript 配置启用 ES2022 目标与严格模式，通过 `isolatedModules` 和 `moduleResolution: "bundler"` 优化 Vite 集成，路径别名 `@/*` 映射至项目根目录以简化模块引用。构建流程通过 `vite build`、`vite build --mode test` 与 `vite build` 三条命令分别支持开发、测试与生产环境打包，配合环境变量注入机制（如 `VITE_API_BASE_URL`）实现多环境配置管理。

Sources: [package.json](package.json#L1-L51) [tsconfig.json](tsconfig.json#L1-L34) [vite.config.ts](vite.config.ts#L1-L39)

## 状态管理与数据流架构

应用采用 **Zustand** 作为全局状态管理方案，相比 Redux 其零样板代码与 hooks-first 设计显著降低认知负担。`useAppStore` 集中管理认证状态（token、user、isAuthenticated）与核心业务动作（login、logout、restoreSession），通过 `create` API 实现类型安全的状态切片。与此同时，**TanStack Query v5** 负责服务端数据缓存与同步，在 `main.tsx` 中通过 `QueryClientProvider` 注入全局查询客户端，为 legacy 会议 BI 模块及后续数据页面提供统一的缓存失效、后台更新与重试策略。这种"全局状态 Zustand + 服务端状态 React Query"的分层架构有效分离客户端与服务端数据关注点。

Sources: [src/stores/useAppStore.ts](src/stores/useAppStore.ts#L1-L76) [src/main.tsx](src/main.tsx#L1-L23)

## 路由与页面注册机制

**React Router v6** 提供声明式路由能力，`BrowserRouter` 在应用根组件包裹整个视图树，配合 `basename` 属性适配 Vite 的 `base` 配置以支持子路径部署。项目实现了一套**类型安全的页面注册系统**：`navigation.ts` 从 `navigationData` 数据源派生路径映射（`PAGE_PATHS`）、标题映射（`PAGE_TITLES`）与实现状态（`IMPLEMENTED_PAGES`），确保路由定义的唯一性与类型一致性。`pageRegistry.tsx` 通过 React.lazy 实现页面级代码分割，每个业务视图（如 `DashboardView`、`MedicalAIWorkbench`）作为独立 chunk 按需加载，配合 `Suspense` 与 `PageLoadingFallback` 优化加载体验。这种数据驱动的路由架构使得新增页面只需在 `navigationData` 中声明定义，即可自动生成路径、导航项与权限检查逻辑。

Sources: [src/navigation.ts](src/navigation.ts#L1-L68) [src/pageRegistry.tsx](src/pageRegistry.tsx#L1-L80) [src/App.tsx](src/App.tsx#L1-L200)

## 网络层与鉴权机制

**Axios** 作为 HTTP 客户端基础，通过工厂函数 `createClient` 创建两个独立实例：`apiClient`（30s 超时，主 API）与 `businessClient`（15s 超时，业务编排层）。核心特性包括：**请求拦截器**自动注入 `CToken`、`DeviceId` 与 `X-User-Id` 头部；**响应拦截器**实现 401 错误的自动 Token 刷新逻辑，通过共享 `refreshPromise` 防止多个并发请求重复触发刷新；**全局登出事件**（`auth:logout`）在 Token 失效时广播至应用层，由 `App.tsx` 统一监听并清理状态。`jwt-decode` 库用于解析 JWT payload 验证 Token 有效性，配合 `authService` 封装登录、IAM 单点登录与会话恢复流程。Vite 开发服务器通过 `proxy` 配置将 `/api/v1` 与 `/api` 请求代理至后端 `VITE_API_BASE_URL`，避免开发环境 CORS 问题。

Sources: [src/services/api.ts](src/services/api.ts#L1-L122) [vite.config.ts](vite.config.ts#L22-L36)

## UI 组件库与样式系统

项目采用 **Ant Design v6** 作为基础组件库，提供表单、表格、模态框等企业级 UI 原语，配合 `@ant-design/icons` 补充图标体系。**Tailwind CSS v4** 通过 `@tailwindcss/vite` 插件集成，启用 JIT（Just-In-Time）引擎实现原子化 CSS 按需生成。`index.css` 中通过 `@theme` 指令定义品牌色彩变量（`--color-brand`、`--color-brand-hover` 等），确保设计系统的一致性。`lucide-react` 作为补充图标库提供更现代的线性图标风格，`motion`（原 Framer Motion）为复杂交互提供声明式动画能力。这种"组件库 + 原子化 CSS + 动画库"的组合平衡了开发效率与定制灵活性。

Sources: [src/index.css](src/index.css#L1-L9) [package.json](package.json#L17-L40)

## 数据可视化与图表集成

**ECharts 6** 作为核心图表库，通过 `echarts-for-react` 封装为 React 组件，在会议 BI 分析、健康数据展示等场景提供交互式可视化能力。ECharts 的声明式配置与 TypeScript 类型定义深度集成，支持动态数据更新与响应式布局适配。项目在 `legacy-meeting-bi` 目录中保留了完整的图表封装体系，通过自定义 hooks 管理图表实例生命周期与数据流。

Sources: [package.json](package.json#L28-L29)

## 工具库与辅助依赖

**dayjs** 替代 Moment.js 提供轻量级日期处理能力（2KB gzip），其链式 API 与插件系统满足时间格式化、相对时间计算等需求。**Zod** 作为运行时类型验证库，在 API 响应校验、表单验证等场景提供类型推导与错误提示。**html-to-image** 支持将 DOM 节点导出为图片，用于报告生成与数据快照分享。**dotenv** 在构建时注入环境变量，配合 Vite 的 `loadEnv` API实现多环境配置管理。

Sources: [package.json](package.json#L26-L39) [vite.config.ts](vite.config.ts#L8-L16)

## AI 能力集成与扩展架构

项目深度集成 **Google GenAI SDK**（`@google/genai`），在健康管家、AI 辅助诊断等模块提供大语言模型对话能力。**@json-render/core** 与 **@json-render/react** 构成 UI Builder 可视化系统的核心，通过 JSON Schema 驱动的组件渲染实现低代码页面搭建。这种"AI + 低代码"的组合为业务人员提供自定义工作台的能力，同时保持技术团队对核心架构的控制权。

Sources: [package.json](package.json#L18-L20)

## 依赖架构全景图

以下表格按功能域分类展示核心依赖的技术选型与职责边界：

| 功能域 | 依赖项 | 版本 | 核心职责 |
|--------|--------|------|----------|
| **框架运行时** | React | 19.0.0 | 声明式 UI 渲染引擎 |
| | React DOM | 19.0.0 | 浏览器渲染器 |
| | TypeScript | 5.8.2 | 静态类型系统 |
| **构建工具** | Vite | 6.2.0 | 开发服务器与生产构建 |
| | @vitejs/plugin-react | 5.0.4 | React Fast Refresh 支持 |
| **路由导航** | react-router-dom | 6.30.1 | 声明式路由管理 |
| **状态管理** | Zustand | 4.5.0 | 轻量级全局状态 |
| | TanStack Query | 5.95.2 | 服务端数据缓存 |
| **UI 框架** | Ant Design | 6.3.4 | 企业级组件库 |
| | Tailwind CSS | 4.1.14 | 原子化 CSS 引擎 |
| | lucide-react | 0.546.0 | 现代图标库 |
| | motion | 12.23.24 | 声明式动画库 |
| **网络请求** | Axios | 1.7.0 | HTTP 客户端 |
| | jwt-decode | 4.0.0 | JWT 解析工具 |
| **数据可视化** | ECharts | 6.0.0 | 交互式图表库 |
| | echarts-for-react | 3.0.6 | React 封装层 |
| **工具库** | dayjs | 1.11.20 | 日期时间处理 |
| | Zod | 4.3.6 | 运行时类型验证 |
| | html-to-image | 1.11.13 | DOM 导出图片 |
| **AI 集成** | @google/genai | 1.29.0 | Google 大模型 SDK |
| | @json-render/react | 0.16.0 | JSON 驱动 UI 渲染 |

Sources: [package.json](package.json#L16-L50)

## 技术栈选型原则

项目技术选型遵循以下核心原则：**类型安全优先**，从 TypeScript 严格模式到 Zod 运行时校验构建全链路类型保障；**开发体验驱动**，Vite 的快速 HMR、Tailwind 的即时样式反馈、React Query 的自动缓存显著提升迭代效率；**生产性能导向**，代码分割、Tree Shaking、JIT 编译确保构建产物精简；**渐进式架构**，Zustand 的极简 API 允许从小规模状态管理起步，React Query 的声明式数据获取降低服务端集成复杂度。这种技术栈组合在保证企业级应用稳定性的同时，为团队提供足够的扩展空间与技术演进能力。

## 下一步阅读建议

掌握技术栈全貌后，建议按以下路径深入理解核心机制：

1. **[JWT 认证与会话恢复机制](5-jwt-ren-zheng-yu-hui-hua-hui-fu-ji-zhi)** - 理解 Token 生命周期管理与自动刷新策略
2. **[Zustand 全局状态管理](7-zustand-quan-ju-zhuang-tai-guan-li)** - 学习状态仓库的设计模式与最佳实践
3. **[类型安全的路由架构](8-lei-xing-an-quan-de-lu-you-jia-gou)** - 掌握数据驱动路由的实现原理
4. **[Axios 客户端封装与拦截器](11-axios-ke-hu-duan-feng-zhuang-yu-lan-jie-qi)** - 深入网络层的工程化封装
5. **[Tailwind CSS 配置](25-tailwind-css-pei-zhi)** - 了解原子化 CSS 的定制化配置