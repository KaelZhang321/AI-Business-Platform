// 模拟数据文件：为演示页面提供功能模块、任务、公告等假数据。
import {
  UserCheck, CalendarClock, Pill, ClipboardCheck, PackageMinus,
  HeartPulse, Car, FileText, CheckSquare, BarChart2, Zap, Layers
} from 'lucide-react';

export const SYSTEMS = [
  { id: 1, name: '到院接待', icon: UserCheck, count: 2, color: 'text-brand', bg: 'bg-brand', text: 'text-white' },
  { id: 2, name: '预约管理', icon: CalendarClock, count: 5, color: 'text-brand' },
  { id: 3, name: '发药管理', icon: Pill, count: 0, color: 'text-orange-400' },
  { id: 4, name: '签到管理', icon: ClipboardCheck, count: 12, color: 'text-brand' },
  { id: 5, name: '消耗管理', icon: PackageMinus, count: 0, color: 'text-red-400' },
  { id: 6, name: '疗效评价', icon: HeartPulse, count: 0, color: 'text-brand' },
  { id: 7, name: '用车申请', icon: Car, count: 0, color: 'text-cyan-400' },
  { id: 8, name: '客户档案', icon: FileText, count: 0, color: 'text-green-500' },
];

export const WORKS = [
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

export const TODOS = [
  {
    id: 1,
    title: '高端客户体检派车确认',
    system: '约车系统',
    sla: '剩余 2 分钟',
    timeRange: '10:00 am - 10:30 am',
    priority: 'high',
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
    priority: 'medium',
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
    priority: 'low',
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

export const NOTICES = [
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

export const RISKS = [
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

export const CUSTOMERS = [
  { id: 1, name: '张三', gender: '男', age: 42, lastCheckDate: '2026-03-18', aiJudgment: '重点关注', keyAbnormal: '空腹血糖 6.4 ↑ / ALT 65 ↑ / 尿酸 435 ↑' },
  { id: 2, name: '李四', gender: '女', age: 36, lastCheckDate: '2026-03-16', aiJudgment: '持续观察', keyAbnormal: '总胆固醇 5.6 ↑ / HDL-C 0.98 ↓' },
  { id: 3, name: '王五', gender: '男', age: 51, lastCheckDate: '2026-03-12', aiJudgment: '平稳正常', keyAbnormal: '关键指标均在参考范围内' },
  { id: 4, name: '赵六', gender: '女', age: 29, lastCheckDate: '2026-03-11', aiJudgment: '优先复查', keyAbnormal: '甲状腺结节随访 / BMI 25.8 ↑ / 收缩压 142 ↑' },
  { id: 5, name: '孙七', gender: '男', age: 45, lastCheckDate: '2026-03-09', aiJudgment: '重点关注', keyAbnormal: '总胆固醇 5.9 ↑ / LDL-C 4.1 ↑ / 血压 148/92 ↑' },
  { id: 6, name: '周八', gender: '女', age: 62, lastCheckDate: '2026-03-08', aiJudgment: '优先复查', keyAbnormal: '骨密度 T值 -2.8 ↓ / 颈动脉斑块形成' },
  { id: 7, name: '吴九', gender: '男', age: 38, lastCheckDate: '2026-03-05', aiJudgment: '持续观察', keyAbnormal: '脂肪肝(轻度) / 甘油三酯 2.1 ↑' },
  { id: 8, name: '郑十', gender: '女', age: 55, lastCheckDate: '2026-03-02', aiJudgment: '重点关注', keyAbnormal: '糖化血红蛋白 7.2% ↑ / 尿微量白蛋白 45 ↑' },
  { id: 9, name: '陈一', gender: '男', age: 27, lastCheckDate: '2026-02-28', aiJudgment: '平稳正常', keyAbnormal: '关键指标均在参考范围内' },
  { id: 10, name: '林二', gender: '女', age: 48, lastCheckDate: '2026-02-25', aiJudgment: '持续观察', keyAbnormal: '乳腺结节 BI-RADS 3类 / 促甲状腺激素 5.2 ↑' },
  { id: 11, name: '何三', gender: '男', age: 59, lastCheckDate: '2026-02-20', aiJudgment: '优先复查', keyAbnormal: '前列腺特异性抗原(PSA) 4.8 ↑ / 肺部小结节' },
  { id: 12, name: '郭四', gender: '女', age: 33, lastCheckDate: '2026-02-18', aiJudgment: '平稳正常', keyAbnormal: '轻度贫血 HGB 105 ↓' },
  { id: 13, name: '马五', gender: '男', age: 66, lastCheckDate: '2026-02-15', aiJudgment: '重点关注', keyAbnormal: '冠脉钙化积分 350 ↑ / 血压 155/95 ↑' },
  { id: 14, name: '罗六', gender: '女', age: 41, lastCheckDate: '2026-02-10', aiJudgment: '持续观察', keyAbnormal: '幽门螺旋杆菌(Hp) 阳性 / 胃蛋白酶原I 65 ↓' },
  { id: 15, name: '高七', gender: '男', age: 31, lastCheckDate: '2026-02-05', aiJudgment: '平稳正常', keyAbnormal: '关键指标均在参考范围内' },
];

export const FUNCTION_MODULES = {
  latest: [
    { id: 15, title: 'AI四象限健康评估', desc: '多维数据建模，通过四象限分析法直观评估患者健康风险等级', icon: 'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&q=80&w=1200&h=800', tag: '评估' },
    { id: 7, title: 'AI报告对比', desc: '秒级解读复杂检验报告，将专业术语转化为易懂的健康建议', icon: 'https://images.unsplash.com/photo-1579154204601-01588f351e67?auto=format&fit=crop&q=80&w=1200&h=800', tag: '智能解读' },
    { id: 3, title: 'AI消耗规划', desc: '智能预测医疗耗材使用趋势，优化库存周转，降低院内物流成本', icon: 'https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&q=80&w=400&h=200', tag: '运营管理' },
    { id: 18, title: 'AI方案推荐', desc: '基于海量临床案例库，智能匹配并推荐最优治疗方案，辅助医生科学决策', icon: 'https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&q=80&w=400&h=200', tag: '精准医疗' },
  ],
  recommended: [
    { id: 1, title: 'AI辅助诊断', desc: '基于深度学习算法，辅助医生快速识别医学影像异常，提升诊断准确率', icon: 'https://images.unsplash.com/photo-1530497610245-94d3c16cda28?auto=format&fit=crop&q=80&w=400&h=200', tag: '智能医疗' },
    { id: 2, title: 'AI干预方案', desc: '根据患者病历与实时体征，自动生成个性化干预建议与治疗路径', icon: 'https://images.unsplash.com/photo-1576091160550-2173dba999ef?auto=format&fit=crop&q=80&w=400&h=200', tag: '临床决策' },
    { id: 4, title: 'AI治疗提醒', desc: '智能监测治疗进度，自动推送用药及复查提醒，保障治疗连续性', icon: 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?auto=format&fit=crop&q=80&w=100&h=100', tag: '患者管理' },
    { id: 5, title: 'AI不良反应预警', desc: '实时分析用药反馈，提前识别潜在不良反应风险并触发预警', icon: 'https://images.unsplash.com/photo-1583947215259-38e31be8751f?auto=format&fit=crop&q=80&w=100&h=100', tag: '用药安全' },
    { id: 6, title: 'AI查房助手', desc: '语音录入查房记录，自动提取关键体征数据，生成标准化查房简报', icon: 'https://images.unsplash.com/photo-1516549655169-df83a0774514?auto=format&fit=crop&q=80&w=100&h=100', tag: '提效工具' },
    { id: 8, title: 'AI病历生成', desc: '基于问诊对话自动生成结构化电子病历，减少医生文书工作量', icon: 'https://images.unsplash.com/photo-1450101499163-c8848c66ca85?auto=format&fit=crop&q=80&w=100&h=100', tag: '文书辅助' },
    { id: 9, title: 'AI疗效预测', desc: '利用大数据模型预测不同治疗方案的预后效果，辅助方案优选', icon: 'https://images.unsplash.com/photo-1532938911079-1b06ac7ceec7?auto=format&fit=crop&q=80&w=100&h=100', tag: '精准医疗' },
  ],
  all: [
    { id: 10, title: 'AI时间管理表', desc: '智能排布医生手术、门诊与科研时间，最大化资源利用率', icon: 'https://images.unsplash.com/photo-1506784365847-bbad939e9335?auto=format&fit=crop&q=80&w=100&h=100', tag: '管理' },
    { id: 11, title: 'AI工作量统计', desc: '多维度自动统计医疗团队工作负荷，为绩效考核提供客观依据', icon: 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&q=80&w=100&h=100', tag: '管理' },
    { id: 12, title: 'AI配液建议', desc: '基于药理学模型，智能推荐静脉配液方案，降低配伍禁忌风险', icon: 'https://images.unsplash.com/photo-1514416432279-50fac261c7dd?auto=format&fit=crop&q=80&w=100&h=100', tag: '临床' },
    { id: 13, title: 'AI随访编排', desc: '根据患者康复进度自动生成随访计划，智能提醒随访节点', icon: 'https://images.unsplash.com/photo-1551076805-e1869033e561?auto=format&fit=crop&q=80&w=100&h=100', tag: '服务' },
    { id: 14, title: 'AI审方系统', desc: '秒级审核处方合理性，自动拦截不合理用药，保障用药安全', icon: 'https://images.unsplash.com/photo-1585435557343-3b092031a831?auto=format&fit=crop&q=80&w=100&h=100', tag: '药事' },
    { id: 16, title: 'AI升单建议', desc: '深度挖掘患者潜在健康需求，智能推荐高价值医疗服务项目', icon: 'https://images.unsplash.com/photo-1557804506-669a67965ba0?auto=format&fit=crop&q=80&w=100&h=100', tag: '经营' },
    { id: 17, title: 'AI话术生成', desc: '针对不同患者类型，自动生成专业且温情的沟通话术，提升转化率', icon: 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&q=80&w=100&h=100', tag: '营销' },
    { id: 18, title: 'AI客户分析', desc: '全方位画像分析，精准识别高价值客户群体，辅助制定经营策略', icon: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&q=80&w=100&h=100', tag: '经营' },
    { id: 19, title: 'AI预约优化', desc: '智能预测预约流量，动态调整排班，减少患者等候时间', icon: 'https://images.unsplash.com/photo-1511174511562-5f7f18b874f8?auto=format&fit=crop&q=80&w=100&h=100', tag: '服务' },
    { id: 20, title: '经营智能问数', desc: '自然语言交互，即时获取经营报表与数据分析，辅助管理决策', icon: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&q=80&w=100&h=100', tag: '管理' },
  ]
};
