本文页帮助你快速掌握前端工程的目录结构与关键文件定位。从根目录入口开始，逐步深入 src 各子目录，厘清组件、页面、服务、数据与配置之间的导航关系，便于后续查阅具体实现。

## 根目录结构概览

根目录包含构建与运行所需的核心配置与产物目录。dist/ 为构建产物，.vite/ 为开发时缓存；.env、.env.example 用于环境变量模板；package.json、tsconfig.json、vite.config.ts 分别管理依赖、TypeScript 编译与 Vite 构建配置。index.html 是单页入口，Dockerfile、DockerVPCfile 与 default.conf 为容器与 Nginx 配置。README.md、metadata.json、remote_deploy.sh、target.txt 属于工程说明与部署辅助。Sources: [package.json](package.json#L1-L51), [tsconfig.json](tsconfig.json#L1-L34), [vite.config.ts](vite.config.ts#L1-L39)

## src 目录导航

src/ 下主要分为：根层应用与路由编排（App.tsx、main.tsx）、页面注册（pageRegistry.tsx）、路由工具（navigation.ts）、全局类型（types.ts）、样式入口（index.css）与环境声明（vite-env.d.ts）。子目录职责明确：components/ 存放业务与通用组件；pages/ 为独立页面模块（如 UI Builder）；services/ 为接口层；stores/ 为状态仓库；data/ 为静态与导航数据源；lib/ 为工具函数；legacy-meeting-bi/ 为独立会议 BI 模块。Sources: [src/main.tsx](src/main.tsx#L1-L23), [src/App.tsx](src/App.tsx#L1-L200), [src/pageRegistry.tsx](src/pageRegistry.tsx#L1-L139), [src/navigation.ts](src/navigation.ts#L1-L68), [src/types.ts](src/types.ts#L1-L80)

## 关键文件与职责

- main.tsx：渲染入口，创建 React Query 客户端与 BrowserRouter，设置路由基础前缀，挂载根组件。Sources: [src/main.tsx](src/main.tsx#L1-L23)
- App.tsx：根组件，负责登录态切换、会话恢复、侧边栏与头部编排、页面渲染分发。Sources: [src/App.tsx](src/App.tsx#L1-L200)
- pageRegistry.tsx：集中管理页面到视图组件的映射，使用懒加载控制首屏包体积，提供统一的渲染入口 renderAppPage。Sources: [src/pageRegistry.tsx](src/pageRegistry.tsx#L1-L139)
- navigation.ts：从导航数据源派生路径映射、标题映射与常用查询工具（getPageByPath、isKnownPath、isImplementedPage 等）。Sources: [src/navigation.ts](src/navigation.ts#L1-L68)
- types.ts：声明系统、任务、公告、消息等页面数据结构类型。Sources: [src/types.ts](src/types.ts#L1-L80)
- vite.config.ts：插件注册、别名 @ 与开发代理配置。Sources: [vite.config.ts](vite.config.ts#L1-L39)

## 子目录用途速查

- components/：业务视图与通用组件。例如 AI 工作台系列、仪表盘、功能广场、侧边栏与头部等。含子模块 consultant-ai-workbench、login-page 等。Sources: [src/components](src/components)
- pages/：独立页面模块。例如 UI Builder（ui-builder/）与 SSO 回调页面（SsoCallback.tsx）。Sources: [src/pages](src/pages)
- services/：接口服务与认证（api.ts、auth.ts）。api.ts 创建带鉴权与自动刷新的 Axios 客户端；auth.ts 封装登录与会话恢复。Sources: [src/services/api.ts](src/services/api.ts#L1-L122), [src/services/auth.ts](src/services/auth.ts)
- stores/：全局状态仓库（Zustand）。useAppStore.ts 管理登录态、用户信息与会话恢复。Sources: [src/stores/useAppStore.ts](src/stores/useAppStore.ts#L1-L76)
- data/：静态数据与导航数据源。navigationData.ts 定义页面元信息、菜单结构、路径与实现标记。Sources: [src/data/navigationData.ts](src/data/navigationData.ts#L1-L190), [src/data/mockData.ts](src/data/mockData.ts)
- lib/：通用工具函数（如导出工具 exportUtils.ts）。Sources: [src/lib/exportUtils.ts](src/lib/exportUtils.ts)
- legacy-meeting-bi/：独立会议 BI 功能模块，包含 api、components、hooks、pages、styles 与 utils。Sources: [src/legacy-meeting-bi](src/legacy-meeting-bi)

## 路由与导航关系

路由以 navigationData.ts 为数据源，通过 navigation.ts 提供工具方法（如 PAGE_PATHS、PAGE_TITLES、getPageByPath）。pageRegistry.tsx 负责将页面类型映射到具体视图组件并使用懒加载。App.tsx 依据路由与认证状态选择渲染登录页或主工作台。Sources: [src/data/navigationData.ts](src/data/navigationData.ts#L1-L190), [src/navigation.ts](src/navigation.ts#L1-L68), [src/pageRegistry.tsx](src/pageRegistry.tsx#L1-L139), [src/App.tsx](src/App.tsx#L1-L200)

## 快速定位指南

- 新增页面：在 data/navigationData.ts 增加页面定义，再在 pageRegistry.tsx 增加渲染器并实现组件。Sources: [src/data/navigationData.ts](src/data/navigationData.ts#L1-L190), [src/pageRegistry.tsx](src/pageRegistry.tsx#L1-L139)
- 调整接口：修改 services/api.ts 的客户端与拦截器，或新增 services/ 文件。Sources: [src/services/api.ts](src/services/api.ts#L1-L122)
- 调整菜单与路径：编辑 data/navigationData.ts，navigation.ts 会自动派生工具方法。Sources: [src/data/navigationData.ts](src/data/navigationData.ts#L1-L190), [src/navigation.ts](src/navigation.ts#L1-L68)
- 全局状态：使用 stores/useAppStore.ts 或新增 store。Sources: [src/stores/useAppStore.ts](src/stores/useAppStore.ts#L1-L76)
- 会议 BI：修改 legacy-meeting-bi/ 下的 api、components、hooks、pages 或 styles。Sources: [src/legacy-meeting-bi](src/legacy-meeting-bi)
- UI Builder：在 pages/ui-builder/ 增加组件与类型。Sources: [src/pages/ui-builder](src/pages/ui-builder)

## 建议阅读路径

- 了解页面注册与懒加载：[页面注册表与懒加载策略](9-ye-mian-zhu-ce-biao-yu-lan-jia-zai-ce-lue)
- 了解路由与导航工具：[类型安全的路由架构](8-lei-xing-an-quan-de-lu-you-jia-gou)
- 了解导航数据源：[动态导航数据源](10-dong-tai-dao-hang-shu-ju-yuan)
- 了解接口层：[Axios 客户端封装与拦截器](11-axios-ke-hu-duan-feng-zhuang-yu-lan-jie-qi)
- 了解状态管理：[Zustand 全局状态管理](7-zustand-quan-ju-zhuang-tai-guan-li)