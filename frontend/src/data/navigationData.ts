// 导航数据源：集中定义页面元信息、菜单结构与占位文案，供路由和侧边栏统一复用。
/** 应用页面标识联合类型 —— 系统中所有可导航页面的唯一标识 */
export type AppPage =
  | 'login'
  | 'dashboard'
  | 'function-square'
  | 'ai-report-comparison'
  | 'health-report'
  | 'ai-four-quadrant'
  | 'ai-component-management'
  | 'ui-builder'
  | 'meeting-bi'
  | 'consultant-ai'
  | 'medical-ai'
  | 'nurse-ai'
  | 'health-butler'
  | 'appointment-ai'
  | 'dispensing-ai'
  | 'deal-management'
  | 'consumption-management'
  | 'client-cloud'
  | 'data-portal'
  | 'meeting-management'
  | 'ai-diagnosis'
  | 'ai-decision'
  | 'ai-rehab'
  | 'customer-search'
  | 'notices'
  | 'settings';

/** 导航图标类型（对应 Lucide 图标名称） */
export type NavigationIcon =
  | 'home'
  | 'layout-dashboard'
  | 'sparkles'
  | 'search'
  | 'file-heart'
  | 'bell'
  | 'settings';

/** 页面定义：每个页面的基本元信息 */
export interface PageDefinition {
  /** URL 路径 */
  path: string;
  /** 中文标题 */
  title: string;
  /** 是否已有真实视图实现 */
  implemented: boolean;
  /** 占位页描述文案（仅未实现页面使用） */
  placeholderDescription?: string;
}

/** 导航菜单项定义：侧边栏一级/二级菜单的结构 */
export interface NavigationItemDefinition {
  /** 对应的页面标识 */
  page: AppPage;
  /** 显示文本 */
  label: string;
  /** 图标名称（可选） */
  icon?: NavigationIcon;
  /** 角标数字（可选） */
  badge?: number;
  /** 子页面标识列表（可选） */
  children?: AppPage[];
}

/** 全量页面定义映射：页面标识 → 元信息配置 */
export const PAGE_DEFINITIONS: Record<AppPage, PageDefinition> = {
  login: { path: '/login', title: '登录', implemented: false },
  dashboard: { path: '/', title: 'AI业务工作台', implemented: true },
  'function-square': { path: '/function-square', title: '功能广场', implemented: true },
  'ai-report-comparison': {
    path: '/ai-report-comparison',
    title: 'AI报告对比',
    implemented: true,
  },
  'health-report': {
    path: '/health-report',
    title: '体检报告',
    implemented: true,
  },
  'ai-four-quadrant': {
    path: '/ai-four-quadrant',
    title: 'AI四象限健康评估',
    implemented: true,
  },
  'ai-component-management': {
    path: '/ai-component-management',
    title: 'AI组件管理',
    implemented: true,
  },
  'ui-builder': { path: '/ui-builder', title: 'JSON Render Builder', implemented: true },
  'meeting-bi': { path: '/meeting-bi', title: '会议BI', implemented: true },
  'consultant-ai': { path: '/consultant-ai', title: '我的AI工作台', implemented: true },
  'medical-ai': { path: '/medical-ai', title: '医疗AI工作台', implemented: true },
  'nurse-ai': { path: '/nurse-ai', title: '护士AI工作台', implemented: true },
  'health-butler': { path: '/health-butler', title: '健康管家AI', implemented: true },
  'appointment-ai': {
    path: '/appointment-ai',
    title: '预约管理AI',
    implemented: false,
    placeholderDescription: '这里会承接预约排班、到院状态跟踪与自动提醒等能力。',
  },
  'dispensing-ai': {
    path: '/dispensing-ai',
    title: '发药管理AI',
    implemented: false,
    placeholderDescription: '这里会承接发药流程、医嘱核对与药品发放记录等能力。',
  },
  'deal-management': {
    path: '/deal-management',
    title: '成交管理AI',
    implemented: false,
    placeholderDescription: '这里会承接客户成交跟进、方案转化与阶段复盘等能力。',
  },
  'consumption-management': {
    path: '/consumption-management',
    title: '消耗管理AI',
    implemented: false,
    placeholderDescription: '这里会承接耗材消耗、库存联动与异常预警等能力。',
  },
  'client-cloud': {
    path: '/client-cloud',
    title: '客户云仓',
    implemented: false,
    placeholderDescription: '这里会承接客户云仓库存、出入库记录与库存查询等能力。',
  },
  'data-portal': {
    path: '/data-portal',
    title: '数据门户',
    implemented: false,
    placeholderDescription: '这里会承接经营数据、客户数据与服务数据的统一门户。',
  },
  'meeting-management': {
    path: '/meeting-management',
    title: '会议管理',
    implemented: false,
    placeholderDescription: '这里会承接晨会、会诊和专题会议的智能管理能力。',
  },
  'ai-diagnosis': { path: '/ai-diagnosis', title: 'AI辅助诊断', implemented: true },
  'ai-decision': {
    path: '/ai-decision',
    title: 'AI辅助决策',
    implemented: false,
    placeholderDescription: '这里会承接辅助决策、方案比对与风险提示等能力。',
  },
  'ai-rehab': {
    path: '/ai-rehab',
    title: 'AI辅助康复',
    implemented: false,
    placeholderDescription: '这里会承接康复计划生成、执行跟踪与阶段评估等能力。',
  },
  'customer-search': {
    path: '/customer-search',
    title: '客户查询',
    implemented: false,
    placeholderDescription: '这里会承接客户档案检索、标签筛选与历史记录查询等能力。',
  },
  notices: {
    path: '/notices',
    title: '通知公告',
    implemented: false,
    placeholderDescription: '这里会承接公告通知、制度下发与消息提醒的统一查看入口。',
  },
  settings: {
    path: '/settings',
    title: '工作台设置',
    implemented: false,
    placeholderDescription: '这里会承接工作台主题、权限配置与个性化设置能力。',
  },
};

/** 主导航菜单项列表（侧边栏上部） */
export const NAVIGATION_ITEMS: NavigationItemDefinition[] = [
  {
    page: 'dashboard',
    label: '首页',
    icon: 'home',
  },
  {
    page: 'function-square',
    label: 'AI智能驾驶舱',
    icon: 'layout-dashboard',
    children: [
      'consultant-ai',
      'medical-ai',
      'nurse-ai',
      'health-butler',
      'meeting-bi',
      'appointment-ai',
      'dispensing-ai',
      'deal-management',
      'consumption-management',
      'client-cloud',
      'data-portal',
      'meeting-management',
    ],
  },
  {
    page: 'ai-component-management',
    label: 'AI组件管理',
    icon: 'sparkles',
  },
  {
    page: 'ai-diagnosis',
    label: '特色服务',
    icon: 'sparkles',
    children: ['ai-diagnosis', 'ai-decision', 'ai-rehab'],
  },
  {
    page: 'customer-search',
    label: '客户查询',
    icon: 'search',
  },
  {
    page: 'health-report',
    label: '体检报告',
    icon: 'file-heart',
  },
];

/** 底部导航菜单项列表（侧边栏下方） */
export const FOOTER_NAVIGATION_ITEMS: NavigationItemDefinition[] = [
  {
    page: 'ui-builder',
    label: 'UI Builder',
    icon: 'layout-dashboard',
  },
  {
    page: 'notices',
    label: '通知公告',
    icon: 'bell',
    badge: 3,
  },
  {
    page: 'settings',
    label: '工作台设置',
    icon: 'settings',
  },
];
