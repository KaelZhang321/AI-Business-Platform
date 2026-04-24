// 常量数据文件：提供首页和工作台中复用的基础静态配置。
import { 
  UserCheck, CalendarClock, Pill, ClipboardCheck, PackageMinus, HeartPulse, Car, FileText,
  AlertTriangle, Info, CheckCircle2, AlertCircle
} from 'lucide-react';
import { System, Work, Todo, Notice, Risk } from './types';

export const SYSTEMS: System[] = [
  { id: 1, name: '到院接待', icon: UserCheck, count: 2, color: 'text-brand', bg: 'bg-brand', text: 'text-white' },
  { id: 2, name: '预约管理', icon: CalendarClock, count: 5, color: 'text-brand' },
  { id: 3, name: '发药管理', icon: Pill, count: 0, color: 'text-orange-400' },
  { id: 4, name: '签到管理', icon: ClipboardCheck, count: 12, color: 'text-brand' },
  { id: 5, name: '消耗管理', icon: PackageMinus, count: 0, color: 'text-red-400' },
  { id: 6, name: '疗效评价', icon: HeartPulse, count: 0, color: 'text-brand' },
  { id: 7, name: '用车申请', icon: Car, count: 0, color: 'text-cyan-400' },
  { id: 8, name: '客户档案', icon: FileText, count: 0, color: 'text-brand' },
];

export const WORKS: Work[] = [
  { 
    id: 1, 
    title: '本周VIP客户回访计划', 
    system: 'CRM系统',
    sla: '今日 17:00 前', 
    timeRange: '08:30 am - 11:20 am',
    priority: 'medium',
    progress: 46,
    description: '需完成5位A级客户的电话回访，并记录在CRM系统中。',
    completed: false,
    theme: 'green',
    comments: 2,
    attachments: 5,
    assignees: ['https://i.pravatar.cc/150?u=1', 'https://i.pravatar.cc/150?u=2', 'https://i.pravatar.cc/150?u=3']
  },
  { 
    id: 2, 
    title: 'Q1季度健康管理报告撰写', 
    system: '健康档案',
    sla: '本周五前', 
    timeRange: '01:00 pm - 03:30 pm',
    priority: 'low',
    progress: 10,
    description: '整理客户体检数据及健康干预效果，生成Q1季度报告。',
    completed: false,
    theme: 'orange',
    comments: 0,
    attachments: 1,
    assignees: ['https://i.pravatar.cc/150?u=4']
  },
  { 
    id: 3, 
    title: '新增医疗设备采购审批', 
    system: 'OA审批',
    sla: '剩余 3 天', 
    timeRange: '04:00 pm - 05:30 pm',
    priority: 'high',
    progress: 80,
    description: '核对采购清单及预算说明，完成OA审批流程。',
    completed: false,
    theme: 'red',
    comments: 4,
    attachments: 2,
    assignees: ['https://i.pravatar.cc/150?u=5', 'https://i.pravatar.cc/150?u=6']
  },
  { 
    id: 4, 
    title: '上月客户满意度调查分析', 
    system: '数据中心',
    sla: '已完成', 
    timeRange: '08:30 am - 09:30 am',
    priority: 'low',
    progress: 100,
    description: '输出分析报告并提交管理层。',
    completed: true,
    theme: 'gray',
    comments: 1,
    attachments: 3,
    assignees: ['https://i.pravatar.cc/150?u=7']
  }
];

export const TODOS: Todo[] = [
  { 
    id: 1, 
    title: '高端客户体检派车确认', 
    system: '约车系统',
    sla: '剩余 2 分钟', 
    timeRange: '10:00 am - 10:30 am',
    priority: 'high', // Red
    progress: 90,
    description: 'A级派车规范：需在预约成功后10分钟内完成派车确认。',
    completed: false,
    theme: 'red',
    comments: 3,
    attachments: 0,
    assignees: ['https://i.pravatar.cc/150?u=8']
  },
  { 
    id: 2, 
    title: '王先生云仓库存盘点', 
    system: '客户云仓',
    sla: '剩余 2 小时', 
    timeRange: '11:00 am - 12:30 pm',
    priority: 'medium', // Yellow/Orange
    progress: 75,
    description: '季度常规盘点，需核对高价值营养品出入库记录。',
    completed: false,
    theme: 'orange',
    comments: 1,
    attachments: 2,
    assignees: ['https://i.pravatar.cc/150?u=9', 'https://i.pravatar.cc/150?u=10']
  },
  { 
    id: 3, 
    title: '市场部报销单据审核', 
    system: '结算中台',
    sla: '剩余 1 天', 
    timeRange: '02:00 pm - 04:00 pm',
    priority: 'low', // Normal
    progress: 30,
    description: '常规财务审核流程。',
    completed: false,
    theme: 'green',
    comments: 0,
    attachments: 4,
    assignees: ['https://i.pravatar.cc/150?u=11']
  },
  { 
    id: 4, 
    title: '更新前台接待SOP手册', 
    system: '知识库',
    sla: '已完成', 
    timeRange: '04:30 pm - 05:00 pm',
    priority: 'low', 
    progress: 100,
    description: '根据最新防疫要求更新接待流程。',
    completed: true,
    theme: 'gray',
    comments: 2,
    attachments: 1,
    assignees: ['https://i.pravatar.cc/150?u=12']
  }
];

export const NOTICES: Notice[] = [
  {
    id: 1,
    title: '关于优化高端客户接待SOP的通知',
    date: '2026-03-16',
    aiSummary: '核心三点：1. 增加专车接送提前确认环节；2. 优化云仓礼品发放流程；3. 缩短客户等待SLA至5分钟。',
    read: false
  },
  {
    id: 2,
    title: '2026年度第一季度合规审查红头文件',
    date: '2026-03-10',
    aiSummary: '强调数据隐私保护，严禁跨权限导出老客户CRM数据，违规将触发红色告警。',
    read: true
  },
  {
    id: 3,
    title: '系统升级：AI 智能调度模块上线',
    date: '2026-03-08',
    aiSummary: '新增运力预测功能，支持根据历史数据自动规划最优派车路线。',
    read: true
  }
];

export const RISKS: Risk[] = [
  { 
    id: 1, 
    title: '数据库连接异常', 
    system: '核心系统',
    sla: '立即处理', 
    priority: 'high',
    progress: 10,
    description: '目前系统与数据库连接出现问题，正在紧急修复中。',
    completed: false,
    theme: 'red'
  },
  { 
    id: 2, 
    title: '新隐私政策发布', 
    system: '合规中心',
    sla: '需确认', 
    priority: 'medium',
    progress: 50,
    description: '我们更新了隐私政策，以确保更好地保护您的个人信息。',
    completed: false,
    theme: 'blue'
  },
  { 
    id: 3, 
    title: '支付成功通知', 
    system: '结算中台',
    sla: '已入账', 
    priority: 'low',
    progress: 100,
    description: '您的款项已成功收到，现已解锁高级会员服务。',
    completed: true,
    theme: 'green',
    link: '查看支付详情'
  },
  { 
    id: 4, 
    title: '系统版本 2.0 已上线', 
    system: '技术部',
    sla: '建议更新', 
    priority: 'medium',
    progress: 90,
    description: '全新 AI 调度引擎已上线，带来更智能的派车体验。',
    completed: false,
    theme: 'yellow'
  }
];
