/** AI 四象限模块可导航的页面标识 */
export type AIFourQuadrantPage =
  | 'dashboard'
  | 'health-butler'
  | 'function-square'
  | 'ai-diagnosis'
  | 'ai-report-comparison-detail'
  | 'ai-four-quadrant'

/** AI 四象限视图组件属性 */
export interface AIFourQuadrantViewProps {
  /** 页面切换回调 */
  setCurrentPage: (page: AIFourQuadrantPage) => void
  /** 是否暗色模式 */
  isDarkMode: boolean
  /** 切换暗色模式 */
  setIsDarkMode: (value: boolean) => void
  /** 是否隐藏头部（内嵌模式） */
  hideHeader?: boolean
  /** 从其他页面传入的导航参数 */
  navigationParams?: {
    customerId?: string | number
    customerName?: string
    [key: string]: unknown
  }
}

/** 客户选项（选择器下拉列表中的单条数据） */
export interface ClientOption {
  /** 客户 ID */
  id: string
  /** 客户姓名 */
  name: string
  /** 性别 */
  gender?: string
  /** 年龄 */
  age?: number
  /** 手机号（脱敏） */
  phone: string
  /** 头像 URL */
  avatar: string
  /** 加密身份证号（可选） */
  encryptedIdCard?: string | null
}

/** 体检报告选项（报告选择器中的单条数据） */
export interface ReportOption {
  /** 报告 ID */
  id: string
  /** 报告标题 */
  title: string
  /** 报告日期 */
  date: string
  /** 体检记录编号（可选） */
  studyId?: string
}

/** 象限内的单个条目 */
export interface QuadrantItem {
  /** 条目唯一 ID */
  id: string
  /** 条目文本内容 */
  content: string
  /** 分类标签（如 abnormal / recommendation） */
  category?: string
}

/** 四象限键名类型：监测 / 干预 / 维护 / 预防 */
export type QuadrantKey = 'monitoring' | 'intervention' | 'maintenance' | 'prevention'

/** 四象限数据结构：每个象限对应一个条目列表 */
export type QuadrantData = Record<QuadrantKey, QuadrantItem[]>

/** 分析结果快照：完整保存一次四象限评估的所有输出 */
export interface AnalysisResultSnapshot {
  /** 监测象限条目 */
  monitoring: QuadrantItem[]
  /** 干预象限条目 */
  intervention: QuadrantItem[]
  /** 维护象限条目 */
  maintenance: QuadrantItem[]
  /** 预防象限条目 */
  prevention: QuadrantItem[]
  /** AI 综合结论 */
  conclusion: string
  /** 客户信息摘要 */
  clientInfo: string
  /** 关联报告信息 */
  reportInfo: string
  /** 风险等级描述 */
  riskLevel: string
  /** 综合健康评分 */
  score: number
}

/** 问诊聊天消息 */
export interface ChatMessage {
  /** 消息 ID */
  id: number
  /** 发送者：ai / user */
  sender: 'ai' | 'user'
  /** 消息文本 */
  text: string
}
