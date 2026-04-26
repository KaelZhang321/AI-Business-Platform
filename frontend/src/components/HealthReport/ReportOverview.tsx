import React from 'react';
import { motion } from 'motion/react';
import { AlertTriangle, AlertCircle, Info, FileText, TrendingDown, Shield } from 'lucide-react';
import type { ConclusionItem, HealthReportData } from '../../types/healthReport';

interface ReportOverviewProps {
  data: HealthReportData;
}

const SEVERITY_CONFIG = {
  critical: {
    border: 'border-red-200 dark:border-red-700/60',
    bg: 'bg-red-50 dark:bg-red-950/25',
    icon: AlertTriangle,
    iconColor: 'text-red-500',
    badge: 'bg-red-100 text-red-700 dark:bg-red-900/60 dark:text-red-300',
    badgeText: '需关注',
  },
  warning: {
    border: 'border-orange-200 dark:border-orange-700/60',
    bg: 'bg-orange-50 dark:bg-orange-950/25',
    icon: AlertCircle,
    iconColor: 'text-orange-500',
    badge: 'bg-orange-100 text-orange-700 dark:bg-orange-900/60 dark:text-orange-300',
    badgeText: '需复查',
  },
  info: {
    border: 'border-slate-200 dark:border-slate-700/60',
    bg: 'bg-slate-50 dark:bg-slate-800/40',
    icon: Info,
    iconColor: 'text-slate-400',
    badge: 'bg-slate-100 text-slate-600 dark:bg-slate-700/60 dark:text-slate-300',
    badgeText: '参考',
  },
};

function ConclusionCard({ item, index }: { key?: React.Key; item: ConclusionItem; index: number }) {
  const cfg = SEVERITY_CONFIG[item.severity];
  const Icon = cfg.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03, duration: 0.2 }}
      className={`flex items-start gap-3 px-4 py-3 rounded-xl border ${cfg.border} ${cfg.bg} transition-all duration-150 hover:shadow-sm`}
    >
      <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${cfg.iconColor}`} />
      <span className="flex-1 min-w-0 text-sm text-slate-700 dark:text-slate-200 leading-relaxed">{item.text}</span>
      <span className={`shrink-0 text-xs font-semibold px-2 py-0.5 rounded-full ${cfg.badge}`}>
        {cfg.badgeText}
      </span>
    </motion.div>
  );
}

export function ReportOverview({ data }: ReportOverviewProps) {
  const criticalCount = data.conclusions.filter(c => c.severity === 'critical').length;
  const warningCount = data.conclusions.filter(c => c.severity === 'warning').length;

  return (
    <div className="space-y-5">
      {/* Stats Cards — abnormal emphasized with larger size */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          icon={AlertTriangle} label="异常项目" value={data.totalAbnormal}
          color="text-red-600 dark:text-red-400" bg="bg-red-50 dark:bg-red-950/30"
          iconBg="bg-red-100 dark:bg-red-900/50"
          emphasis
        />
        <StatCard
          icon={AlertCircle} label="需关注" value={criticalCount + warningCount}
          color="text-orange-600 dark:text-orange-400" bg="bg-orange-50 dark:bg-orange-950/30"
          iconBg="bg-orange-100 dark:bg-orange-900/50"
        />
        <StatCard
          icon={FileText} label="检查项目" value={data.totalItems}
          color="text-brand" bg="bg-brand/5 dark:bg-brand/10"
          iconBg="bg-brand/10 dark:bg-brand/20"
        />
        <StatCard
          icon={Shield} label="正常项目" value={data.totalItems - data.totalAbnormal}
          color="text-emerald-600 dark:text-emerald-400" bg="bg-emerald-50 dark:bg-emerald-950/30"
          iconBg="bg-emerald-100 dark:bg-emerald-900/50"
        />
      </div>

      {/* Final Conclusions */}
      <div className="bg-white/50 dark:bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-slate-200/60 dark:border-slate-700/60 p-5">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-4 flex items-center gap-2">
          <FileText className="w-4 h-4 text-brand" />
          体检结论
          <span className="text-xs font-normal text-slate-400 dark:text-slate-500">共 {data.conclusions.length} 项</span>
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-2.5">
          {data.conclusions.map((item, i) => (
            <ConclusionCard key={item.index} item={item} index={i} />
          ))}
        </div>
      </div>

      {/* Abnormal Summary */}
      <div className="bg-white/50 dark:bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-slate-200/60 dark:border-slate-700/60 p-5">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-4 flex items-center gap-2">
          <TrendingDown className="w-4 h-4 text-orange-500" />
          各科室异常摘要
        </h3>
        <div className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed whitespace-pre-line max-h-96 overflow-y-auto custom-scrollbar">
          {data.abnormalSummary.replace(/\r\n/g, '\n')}
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color, bg, iconBg, emphasis }: {
  icon: React.ElementType; label: string; value: number; color: string; bg: string; iconBg: string; emphasis?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
      className={`${bg} rounded-2xl p-4 flex items-center gap-3 ${emphasis ? 'ring-1 ring-red-200 dark:ring-red-800/50' : ''}`}
    >
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${iconBg}`}>
        <Icon className={`w-5 h-5 ${color}`} />
      </div>
      <div>
        <div className={`${emphasis ? 'text-3xl' : 'text-2xl'} font-bold tabular-nums ${color}`}>{value}</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{label}</div>
      </div>
    </motion.div>
  );
}
