import { AlertCircle, UserPlus, Users, Zap } from 'lucide-react';
import type { StatCard } from './types';

export const DETAIL_STATS: StatCard[] = [
  {
    label: '总客户数',
    value: '2,486',
    color: 'text-blue-500',
    dot: 'bg-blue-500',
    desc: '已录入近三年体检数据',
    icon: Users,
    bg: 'bg-gradient-to-br from-white to-blue-50 dark:from-slate-800 dark:to-blue-900/20',
  },
  {
    label: '本周新增',
    value: '126',
    color: 'text-emerald-500',
    dot: 'bg-emerald-500',
    desc: '较上周提升 12%',
    icon: UserPlus,
    bg: 'bg-gradient-to-br from-white to-emerald-50 dark:from-slate-800 dark:to-emerald-900/20',
  },
  {
    label: '异常客户',
    value: '318',
    color: 'text-rose-500',
    dot: 'bg-rose-500',
    desc: '当前指标超出范围',
    icon: AlertCircle,
    bg: 'bg-gradient-to-br from-white to-rose-50 dark:from-slate-800 dark:to-rose-900/20',
  },
  {
    label: 'AI预警',
    value: '73',
    color: 'text-amber-500',
    dot: 'bg-amber-500',
    desc: '建议优先复查与随访',
    icon: Zap,
    bg: 'bg-gradient-to-br from-white to-amber-50 dark:from-slate-800 dark:to-amber-900/20',
  },
];
