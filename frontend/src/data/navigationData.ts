// 导航数据源：集中定义页面元信息、菜单结构与占位文案，供路由和侧边栏统一复用。
export type AppPage =
  | 'login'
  | 'dashboard'
  | 'function-square'
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

export type NavigationIcon =
  | 'home'
  | 'layout-dashboard'
  | 'sparkles'
  | 'search'
  | 'bell'
  | 'settings';

export interface PageDefinition {
  path: string;
  title: string;
  implemented: boolean;
  placeholderDescription?: string;
}

export interface NavigationItemDefinition {
  page: AppPage;
  label: string;
  icon?: NavigationIcon;
  badge?: number;
  children?: AppPage[];
}

export const PAGE_DEFINITIONS: Record<AppPage, PageDefinition> = {
  login: { path: '/login', title: '登录', implemented: false },
  dashboard: { path: '/', title: 'AI业务工作台', implemented: true },
  'function-square': { path: '/function-square', title: '功能广场', implemented: true },
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
];

export const FOOTER_NAVIGATION_ITEMS: NavigationItemDefinition[] = [
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
