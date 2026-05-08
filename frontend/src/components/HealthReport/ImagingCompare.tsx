import React, { useState } from 'react';
import { motion } from 'motion/react';
import { ScanLine, ArrowUpRight, ArrowDownRight, Minus, AlertTriangle, CheckCircle, X, ChevronDown } from 'lucide-react';
import type { ImagingSection } from '../../types/healthReport';

interface ImagingCompareProps {
  currentSections: ImagingSection[];
  previousSections: ImagingSection[];
  currentLabel: string;
  previousLabel: string;
  onClose: () => void;
}

interface ComparedPair {
  title: string;
  current: ImagingSection | null;
  previous: ImagingSection | null;
  changes: ChangeItem[];
}

interface ChangeItem {
  type: 'grading_up' | 'grading_down' | 'grading_same' | 'size_increase' | 'size_decrease' | 'new_finding' | 'resolved' | 'unchanged';
  description: string;
  severity: 'critical' | 'positive' | 'neutral';
}

function extractSizes(text: string): { raw: string; w: number; h: number }[] {
  const regex = /(\d+\.?\d*)cm\s*[×x]\s*(\d+\.?\d*)cm/g;
  const results: { raw: string; w: number; h: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = regex.exec(text)) !== null) {
    results.push({ raw: m[0], w: parseFloat(m[1]), h: parseFloat(m[2]) });
  }
  return results;
}

function compareImagingSections(current: ImagingSection | null, previous: ImagingSection | null): ChangeItem[] {
  if (!current && !previous) return [];
  if (current && !previous) return [{ type: 'new_finding', description: '新增检查项目', severity: 'neutral' }];
  if (!current && previous) return [{ type: 'resolved', description: '本次未检查该项目', severity: 'neutral' }];

  const changes: ChangeItem[] = [];
  const c = current!;
  const p = previous!;

  if (c.grading && p.grading && c.grading.system === p.grading.system) {
    const cLevel = parseInt(c.grading.level);
    const pLevel = parseInt(p.grading.level);
    if (cLevel > pLevel) {
      changes.push({ type: 'grading_up', description: `${c.grading.system} ${pLevel}→${cLevel} 等级上升`, severity: 'critical' });
    } else if (cLevel < pLevel) {
      changes.push({ type: 'grading_down', description: `${c.grading.system} ${pLevel}→${cLevel} 等级下降`, severity: 'positive' });
    } else {
      changes.push({ type: 'grading_same', description: `${c.grading.system} ${cLevel} 等级不变`, severity: 'neutral' });
    }
  } else if (c.grading && !p.grading) {
    changes.push({ type: 'new_finding', description: `新增 ${c.grading.system} ${c.grading.level} 评级`, severity: 'critical' });
  }

  const cSizes = extractSizes(c.description || c.findings);
  const pSizes = extractSizes(p.description || p.findings);
  if (cSizes.length > 0 && pSizes.length > 0) {
    const cMax = cSizes.reduce((a, b) => (a.w * a.h > b.w * b.h ? a : b));
    const pMax = pSizes.reduce((a, b) => (a.w * a.h > b.w * b.h ? a : b));
    if (cMax.w * cMax.h > pMax.w * pMax.h * 1.1) {
      changes.push({ type: 'size_increase', description: `病灶 ${pMax.raw} → ${cMax.raw} 增大`, severity: 'critical' });
    } else if (cMax.w * cMax.h < pMax.w * pMax.h * 0.9) {
      changes.push({ type: 'size_decrease', description: `病灶 ${pMax.raw} → ${cMax.raw} 缩小`, severity: 'positive' });
    }
  }

  const keywords = ['囊肿', '结节', '息肉', '结石', '结晶', '增厚', '肌瘤', '反流'];
  for (const kw of keywords) {
    const inCurrent = c.findings.includes(kw);
    const inPrevious = p.findings.includes(kw);
    if (inCurrent && !inPrevious) changes.push({ type: 'new_finding', description: `新发现：${kw}`, severity: 'critical' });
    else if (!inCurrent && inPrevious) changes.push({ type: 'resolved', description: `已消失：${kw}`, severity: 'positive' });
  }

  if (changes.length === 0) {
    changes.push({ type: 'unchanged', description: '与上次检查无明显变化', severity: 'neutral' });
  }
  return changes;
}

const CHANGE_STYLE: Record<ChangeItem['severity'], { bg: string; text: string; icon: React.ElementType }> = {
  critical: { bg: 'bg-red-50 dark:bg-red-950/30', text: 'text-red-600 dark:text-red-400', icon: ArrowUpRight },
  positive: { bg: 'bg-emerald-50 dark:bg-emerald-950/30', text: 'text-emerald-600 dark:text-emerald-400', icon: ArrowDownRight },
  neutral:  { bg: 'bg-slate-50 dark:bg-slate-800/50', text: 'text-slate-500 dark:text-slate-400', icon: Minus },
};

const TYPE_ICON: Record<string, React.ElementType> = {
  grading_up: ArrowUpRight, grading_down: ArrowDownRight, grading_same: Minus,
  size_increase: ArrowUpRight, size_decrease: ArrowDownRight,
  new_finding: AlertTriangle, resolved: CheckCircle, unchanged: CheckCircle,
};

export function ImagingCompare({ currentSections, previousSections, currentLabel, previousLabel, onClose }: ImagingCompareProps) {
  const allTitles = new Set([...currentSections.map(s => s.title), ...previousSections.map(s => s.title)]);
  const pairs: ComparedPair[] = Array.from(allTitles).map(title => {
    const current = currentSections.find(s => s.title === title) || null;
    const previous = previousSections.find(s => s.title === title) || null;
    return { title, current, previous, changes: compareImagingSections(current, previous) };
  });

  const [expandedPair, setExpandedPair] = useState<string | null>(
    pairs.find(p => p.changes.some(c => c.severity === 'critical'))?.title || pairs[0]?.title || null
  );

  return (
    <div className="space-y-4">
      {/* Compare Header */}
      <div className="flex items-center justify-between p-4 bg-white/50 dark:bg-slate-900/50 rounded-2xl border border-slate-200/60 dark:border-slate-700/60">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-brand ring-2 ring-brand/20" />
            <span className="text-xs font-semibold text-brand">{currentLabel}</span>
            <span className="text-xs text-slate-400">最新</span>
          </div>
          <div className="text-xs text-slate-300 dark:text-slate-600 font-bold">VS</div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-slate-400 ring-2 ring-slate-200 dark:ring-slate-700" />
            <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">{previousLabel}</span>
            <span className="text-xs text-slate-400">上次</span>
          </div>
        </div>
        <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors duration-150">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Comparison Cards */}
      {pairs.map((pair, idx) => {
        const isExpanded = expandedPair === pair.title;
        const hasCritical = pair.changes.some(c => c.severity === 'critical');

        return (
          <motion.div
            key={pair.title}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.04, duration: 0.2 }}
            className={`rounded-2xl border overflow-hidden transition-colors duration-150 ${
              hasCritical
                ? 'border-red-200 dark:border-red-800/60'
                : 'border-slate-200 dark:border-slate-700'
            }`}
          >
            {/* Pair Header */}
            <button
              onClick={() => setExpandedPair(isExpanded ? null : pair.title)}
              className={`w-full flex items-center justify-between px-4 py-3.5 transition-colors duration-150 ${
                isExpanded
                  ? 'bg-white dark:bg-slate-800'
                  : 'bg-white/80 dark:bg-slate-800/80 hover:bg-white dark:hover:bg-slate-800'
              }`}
            >
              <div className="flex items-center gap-3">
                <ScanLine className={`w-4 h-4 shrink-0 ${hasCritical ? 'text-red-500' : 'text-slate-400'}`} />
                <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">{pair.title}</span>
              </div>
              <div className="flex items-center gap-2">
                {/* Show change badges — compact, severity-colored */}
                {pair.changes.slice(0, 3).map((change, ci) => {
                  const style = CHANGE_STYLE[change.severity];
                  const Icon = TYPE_ICON[change.type];
                  return (
                    <span key={ci} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${style.bg} ${style.text}`} title={change.description}>
                      <Icon className="w-3 h-3" />
                      <span className="max-w-[120px] truncate">{change.description}</span>
                    </span>
                  );
                })}
                <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ml-1 ${isExpanded ? 'rotate-180' : ''}`} />
              </div>
            </button>

            {/* Side-by-side Content */}
            {isExpanded && (
              <div className="grid grid-cols-2 divide-x divide-slate-100 dark:divide-slate-700 border-t border-slate-100 dark:border-slate-800">
                {/* Current */}
                <div className="p-5">
                  <div className="text-xs font-semibold text-brand uppercase tracking-wider mb-3">{currentLabel} (最新)</div>
                  {pair.current ? (
                    <div className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed whitespace-pre-line">
                      {pair.current.findings.replace(/\r\n/g, '\n')}
                    </div>
                  ) : (
                    <div className="text-sm text-slate-400 italic py-4">该次体检未检查此项目</div>
                  )}
                  {pair.current?.grading && (
                    <div className="mt-3 inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-brand/10 text-brand border border-brand/20">
                      {pair.current.grading.system} {pair.current.grading.level}
                    </div>
                  )}
                </div>
                {/* Previous */}
                <div className="p-5 bg-slate-50/80 dark:bg-slate-900/40">
                  <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">{previousLabel} (上次)</div>
                  {pair.previous ? (
                    <div className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed whitespace-pre-line">
                      {pair.previous.findings.replace(/\r\n/g, '\n')}
                    </div>
                  ) : (
                    <div className="text-sm text-slate-400 italic py-4">该次体检未检查此项目</div>
                  )}
                  {pair.previous?.grading && (
                    <div className="mt-3 inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                      {pair.previous.grading.system} {pair.previous.grading.level}
                    </div>
                  )}
                </div>
              </div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}
