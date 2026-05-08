import type { AnalysisResultSnapshot, ClientOption, QuadrantData, ReportOption } from './types'

/** 空白四象限数据初始值 */
export const EMPTY_QUADRANT_DATA: QuadrantData = {
  monitoring: [],
  intervention: [],
  maintenance: [],
  prevention: [],
}

/** 分析过程步骤描述（配合进度条动画显示） */
export const ANALYSIS_STEPS = [
  '正在读取体检报告数据...',
  '正在解析医生面诊备注...',
  '正在匹配健康指标基准...',
  '正在进行多维风险评估...',
  '正在生成四象限建议...',
  '分析完成，正在同步结果...',
]

/** 客户模拟数据（用于选择器演示） */
export const MOCK_CLIENTS: ClientOption[] = [
  { id: '1', name: '张美玲', phone: '138****5678', avatar: 'https://i.pravatar.cc/150?u=zhang' },
  { id: '2', name: '张美玲', phone: '139****1234', avatar: 'https://i.pravatar.cc/150?u=wang' },
  { id: '3', name: '张美玲', phone: '137****8888', avatar: 'https://i.pravatar.cc/150?u=li' },
]

/** 报告模拟数据（按客户 ID 分组） */
export const MOCK_REPORTS: Record<string, ReportOption[]> = {
  '1': [
    { id: 'R1', title: '2024年度深度体检报告', date: '2024-03-15' },
    { id: 'R2', title: '2023年度常规体检报告', date: '2023-03-10' },
  ],
  '2': [{ id: 'R3', title: '2024年第一季度健康监测', date: '2024-01-20' }],
  '3': [{ id: 'R4', title: '心血管专项筛查报告', date: '2024-02-28' }],
}

/** 初始分析结果快照（演示用默认值） */
export const INITIAL_ANALYSIS_RESULTS: AnalysisResultSnapshot = {
  monitoring: [
    { id: 'm1', content: '血管抗衰养护 + 重金属螯合' },
    { id: 'm2', content: '代谢管理2025' },
  ],
  intervention: [
    { id: 'i1', content: '粘膜修复', category: 'abnormal' },
    { id: 'i2', content: '菲净素 (肺结节、甲状腺结节)', category: 'abnormal' },
    { id: 'i3', content: '抗衰老方案', category: 'recommendation' },
    { id: 'i4', content: '甲功全项检查', category: 'recommendation' },
  ],
  maintenance: [
    { id: 'ma1', content: '前列腺PET-MRI (PSMA)' },
    { id: 'ma2', content: '男性荷尔蒙调理' },
    { id: 'ma3', content: '食物不耐受90项' },
  ],
  prevention: [{ id: 'p1', content: '菲净素 (肺结节、甲状腺结节)' }],
  conclusion: '已结合体检报告和医生备注，判断心血管风险与脂代谢异常聚集，需优先处理A级-红色健康预警。',
  clientInfo: '张美玲 / 138****5678',
  reportInfo: '2024年度深度体检报告',
  riskLevel: '中高风险',
  score: 68,
}

/** 初始聊天消息（AI 欢迎语） */
export const INITIAL_CHAT_MESSAGES = [
  { id: 1, sender: 'ai' as const, text: '补充问诊备注或调整指令，我会联动右侧结果。' },
]
