import type { AppPage } from '../../../navigation';

/** 已保存的卡片布局方案 */
export type SavedLayout = {
  /** 布局方案 ID */
  id: string;
  /** 布局方案名称 */
  name: string;
  /** 选中的卡片 ID 列表 */
  cards: string[];
  /** 原始保存的布局 JSON */
  cardJson?: string;
  /** 布局类型：固定卡片布局 / 会话返回的结构化 Spec */
  layoutType?: 'cards' | 'spec';
  /** 会话返回的结构化 Spec 内容 */
  specContent?: string | null;
  /** 关联的客户 ID（可选） */
  customerId?: string;
};

/** AI 助手聊天历史记录条目 */
export type ChatHistoryItem = {
  /** 角色：user / assistant */
  role: 'user' | 'assistant';
  /** 聊天内容 */
  content: string;
};

/** AI 分析结果条目 */
export type AIResultItem = {
  /** 结果 ID */
  id: number;
  /** 结果类型标识 */
  type: string;
  /** 结果标题 */
  title: string;
  /** 结果内容 */
  content: string;
};

/** 客户记录（顾问工作台中的客户数据行） */
export type CustomerRecord = {
  /** 客户 ID */
  id: string;
  /** 客户姓名 */
  name: string;
  /** 年龄 */
  age?: number;
  /** 性别 */
  gender?: string;
  /** 手机号 */
  phone?: string;
  /** 身份证号 */
  idCard?: string;
  /** 最近体检日期 */
  lastCheckDate?: string;
  /** AI 判断结论 */
  aiJudgment?: string;
  /** 关键异常指标 */
  keyAbnormal?: string;
  [key: string]: unknown;
};

/** 顾问 AI 工作台组件属性 */
export interface ConsultantAIWorkbenchProps {
  /** 页面切换回调 */
  setCurrentPage?: (page: AppPage) => void;
  /** 设置导航参数回调 */
  setNavigationParams?: (params: Record<string, unknown>) => void;
}
