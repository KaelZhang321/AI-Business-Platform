import React from 'react';
import { ArrowUp, ArrowDown, AlertCircle, CheckCircle } from 'lucide-react';
import type { AbnormalStatus } from '../../types/healthReport';

interface AbnormalBadgeProps {
  status: AbnormalStatus;
  text?: string;
  size?: 'sm' | 'md';
}

const CONFIG: Record<string, {
  bg: string; text: string; icon: React.ElementType; label: string;
}> = {
  high:     { bg: 'bg-red-100 dark:bg-red-900/50', text: 'text-red-700 dark:text-red-300', icon: ArrowUp, label: '偏高' },
  low:      { bg: 'bg-blue-100 dark:bg-blue-900/50', text: 'text-blue-700 dark:text-blue-300', icon: ArrowDown, label: '偏低' },
  positive: { bg: 'bg-orange-100 dark:bg-orange-900/50', text: 'text-orange-700 dark:text-orange-300', icon: AlertCircle, label: '阳性' },
  critical: { bg: 'bg-red-100 dark:bg-red-900/50', text: 'text-red-700 dark:text-red-300', icon: AlertCircle, label: '异常' },
  normal:   { bg: 'bg-emerald-50 dark:bg-emerald-900/40', text: 'text-emerald-700 dark:text-emerald-300', icon: CheckCircle, label: '正常' },
};

export function AbnormalBadge({ status, text, size = 'sm' }: AbnormalBadgeProps) {
  if (!status || status === 'normal') return null;

  const cfg = CONFIG[status] || CONFIG.normal;
  const Icon = cfg.icon;
  const label = text || cfg.label;
  const isSmall = size === 'sm';

  return (
    <span className={`inline-flex items-center gap-1 rounded-full font-semibold ${cfg.bg} ${cfg.text} ${
      isSmall ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
    }`}>
      <Icon className={isSmall ? 'w-3 h-3' : 'w-3.5 h-3.5'} />
      {label}
    </span>
  );
}

interface GradingBadgeProps {
  system: string;
  level: string;
}

export function GradingBadge({ system, level }: GradingBadgeProps) {
  const levelNum = parseInt(level);
  let colorClass = 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300';
  if (levelNum >= 4) colorClass = 'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300';
  else if (levelNum >= 3) colorClass = 'bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-300';
  else if (levelNum >= 2) colorClass = 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/50 dark:text-yellow-300';

  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold ${colorClass}`}>
      {system} {level}
    </span>
  );
}

interface RangeBarProps {
  value: number | null;
  min: number | null;
  max: number | null;
  status: AbnormalStatus;
}

export function RangeBar({ value, min, max, status }: RangeBarProps) {
  if (value === null || min === null || max === null) return null;

  const range = max - min;
  if (range <= 0) return null;

  const extendedMin = min - range * 0.3;
  const extendedMax = max + range * 0.3;
  const extendedRange = extendedMax - extendedMin;
  const pos = Math.max(0, Math.min(100, ((value - extendedMin) / extendedRange) * 100));
  const refStart = ((min - extendedMin) / extendedRange) * 100;
  const refEnd = ((max - extendedMin) / extendedRange) * 100;

  const dotColor = status === 'high' ? 'bg-red-500' : status === 'low' ? 'bg-blue-500' : 'bg-emerald-500';

  return (
    <div className="w-24 h-3.5 relative rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden" title={`${value} (${min}-${max})`}>
      {/* Reference range band */}
      <div
        className="absolute top-0 bottom-0 bg-emerald-100 dark:bg-emerald-900/50"
        style={{ left: `${refStart}%`, width: `${refEnd - refStart}%` }}
      />
      {/* Value dot */}
      <div
        className={`absolute top-0.5 w-2.5 h-2.5 rounded-full ${dotColor} shadow-sm ring-1 ring-white dark:ring-slate-900`}
        style={{ left: `calc(${pos}% - 5px)` }}
      />
    </div>
  );
}
