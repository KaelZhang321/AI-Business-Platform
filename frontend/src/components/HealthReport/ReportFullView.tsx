import React, { useMemo } from 'react';
import { AlertTriangle, ScanLine, FileText } from 'lucide-react';
import type { HealthReportData, ParsedItem, DisplayMode, ImagingSection, ExamRecord } from '../../types/healthReport';
import { AbnormalBadge, RangeBar } from './AbnormalBadge';

interface ReportFullViewProps {
  examRecords: ExamRecord[];       // selected exam records (may be multiple)
  displayMode: DisplayMode;
  searchQuery: string;
}

/** A merged row: one indicator across multiple exams */
interface MergedRow {
  itemCode: string;
  itemName: string;
  itemNameEn: string;
  referenceRange: string;
  refMin: number | null;
  refMax: number | null;
  majorItemName: string | null;
  /** One entry per selected exam, in same order as examRecords */
  values: (ParsedItem | null)[];
  /** Worst abnormal status across all values */
  worstStatus: ParsedItem['abnormalStatus'];
}

interface TableSection {
  id: string;
  title: string;
  type: 'table' | 'imaging' | 'text';
  rows: MergedRow[];
  imagingSections?: { examDate: string; sections: ImagingSection[] }[];
  textItems?: { examDate: string; items: ParsedItem[] }[];
}

function matchesSearch(row: MergedRow, q: string): boolean {
  if (!q) return true;
  const lower = q.toLowerCase();
  return row.itemName.toLowerCase().includes(lower) ||
         row.itemNameEn.toLowerCase().includes(lower) ||
         row.itemCode.includes(lower) ||
         (row.majorItemName || '').toLowerCase().includes(lower);
}

const STATUS_PRIORITY: Record<string, number> = { critical: 4, positive: 3, high: 2, low: 1, normal: 0 };

function worstOf(a: ParsedItem['abnormalStatus'], b: ParsedItem['abnormalStatus']): ParsedItem['abnormalStatus'] {
  return (STATUS_PRIORITY[a || ''] || 0) >= (STATUS_PRIORITY[b || ''] || 0) ? a : b;
}

export function ReportFullView({ examRecords, displayMode, searchQuery }: ReportFullViewProps) {
  const hasMultiple = examRecords.length > 1;
  const validRecords = examRecords.filter(e => !!e.reportData);

  const { abnormalSection, groupSections } = useMemo(() => {
    if (validRecords.length === 0) return { abnormalSection: null, groupSections: [] };

    // Use first record's clinical groups as the structural template
    const template = validRecords[0].reportData;
    const sections: TableSection[] = [];
    const allMergedRows: MergedRow[] = [];

    for (const group of template.clinicalGroups) {
      if (group.type === 'imaging') {
        sections.push({
          id: group.id, title: group.name, type: 'imaging', rows: [],
          imagingSections: validRecords.map(r => ({ examDate: r.examDate, sections: r.reportData.imagingSections })),
        });
        continue;
      }

      if (group.type === 'text') {
        sections.push({
          id: group.id, title: group.name, type: 'text', rows: [],
          textItems: validRecords.map(r => ({
            examDate: r.examDate,
            items: r.reportData.clinicalGroups.find(g => g.id === group.id)?.subGroups.flatMap(s => s.items) || [],
          })),
        });
        continue;
      }

      // Table-type: merge items by itemCode+itemName across exam records
      for (const sub of group.subGroups) {
        const sectionTitle = group.subGroups.length > 1 ? `${group.name} › ${sub.name}` : group.name;

        // Collect items for this sub-group from each exam record
        const perExamItems: ParsedItem[][] = validRecords.map(record => {
          const g = record.reportData.clinicalGroups.find(cg => cg.id === group.id);
          const s = g?.subGroups.find(sg => sg.id === sub.id);
          return s?.items || [];
        });

        // Build merged rows — key by itemCode+itemName
        const rowMap = new Map<string, MergedRow>();
        perExamItems.forEach((items, examIdx) => {
          for (const item of items) {
            const key = `${item.itemCode}|${item.itemName}`;
            if (!rowMap.has(key)) {
              rowMap.set(key, {
                itemCode: item.itemCode,
                itemName: item.itemName,
                itemNameEn: item.itemNameEn,
                referenceRange: item.referenceRange,
                refMin: item.refMin,
                refMax: item.refMax,
                majorItemName: item.majorItemName,
                values: new Array(validRecords.length).fill(null),
                worstStatus: null,
              });
            }
            const row = rowMap.get(key)!;
            row.values[examIdx] = item;
            row.worstStatus = worstOf(row.worstStatus, item.abnormalStatus);
            // Update ref if current has better data
            if (!row.referenceRange && item.referenceRange) {
              row.referenceRange = item.referenceRange;
              row.refMin = item.refMin;
              row.refMax = item.refMax;
            }
          }
        });

        const rows = Array.from(rowMap.values());
        sections.push({ id: `${group.id}-${sub.id}`, title: sectionTitle, type: 'table', rows });
        allMergedRows.push(...rows);
      }
    }

    // Abnormal aggregate
    const abnormalRows = allMergedRows.filter(r => r.worstStatus && r.worstStatus !== 'normal');
    const abnormalSection: TableSection = {
      id: 'abnormal-aggregate',
      title: `异常项目 (${abnormalRows.length})`,
      type: 'table',
      rows: abnormalRows,
    };

    return { abnormalSection, groupSections: sections };
  }, [validRecords]);

  // Filters
  const filterRows = (rows: MergedRow[]) => {
    return rows.filter(row => {
      if (displayMode === 'abnormal' && (!row.worstStatus || row.worstStatus === 'normal')) return false;
      return matchesSearch(row, searchQuery);
    });
  };

  if (validRecords.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-sm text-slate-400 dark:text-slate-500">
        请选择至少一条体检记录
      </div>
    );
  }

  const filteredAbnormal = abnormalSection ? filterRows(abnormalSection.rows) : [];
  const showAbnormalSection = displayMode !== 'abnormal' && filteredAbnormal.length > 0;

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      {/* Column Headers — exam dates (sticky) */}
      {hasMultiple && (
        <div className="sticky top-0 z-20 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border-b border-slate-200 dark:border-slate-700">
          <table className="w-full">
            <thead>
              <tr>
                <th className="pl-4 pr-2 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-400 w-[28%]">项目</th>
                {validRecords.map((record, i) => (
                  <th key={record.id} className={`px-2 py-2 text-center text-xs font-semibold tabular-nums ${
                    i === 0 ? 'text-brand' : 'text-slate-500 dark:text-slate-400'
                  }`}>
                    {record.examDate}
                    {i === 0 && <span className="ml-1 text-[10px] font-normal text-slate-400">(最新)</span>}
                  </th>
                ))}
                <th className="px-2 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-400 w-[14%]">参考范围</th>
                <th className="pr-4 pl-2 py-2 text-center text-xs font-semibold text-slate-500 dark:text-slate-400 w-[8%]">状态</th>
              </tr>
            </thead>
          </table>
        </div>
      )}

      {/* Abnormal Aggregate */}
      {showAbnormalSection && (
        <div className="mb-1">
          <StickyHeader
            icon={<AlertTriangle className="w-3.5 h-3.5 text-red-500" />}
            title={abnormalSection!.title}
            count={filteredAbnormal.length}
            accent="red"
            stickyOffset={hasMultiple ? 'top-[33px]' : 'top-0'}
          />
          <MergedTable rows={filteredAbnormal} examRecords={validRecords} searchQuery={searchQuery} hasMultiple={hasMultiple} />
        </div>
      )}

      {/* All Sections */}
      {groupSections.map(section => {
        if (section.type === 'imaging') {
          const allSections = section.imagingSections?.[0]?.sections || [];
          const filtered = displayMode === 'abnormal' ? allSections.filter(s => s.hasAbnormal) : allSections;
          if (searchQuery) {
            const q = searchQuery.toLowerCase();
            const matched = filtered.filter(s => s.title.toLowerCase().includes(q) || s.findings.toLowerCase().includes(q));
            if (matched.length === 0) return null;
            return (
              <div key={section.id} className="mb-1">
                <StickyHeader icon={<ScanLine className="w-3.5 h-3.5 text-orange-500" />} title={section.title} count={matched.length} accent="orange" stickyOffset={hasMultiple ? 'top-[33px]' : 'top-0'} />
                <ImagingCompactList sections={matched} />
              </div>
            );
          }
          if (filtered.length === 0) return null;
          return (
            <div key={section.id} className="mb-1">
              <StickyHeader icon={<ScanLine className="w-3.5 h-3.5 text-orange-500" />} title={section.title} count={filtered.length} accent="orange" stickyOffset={hasMultiple ? 'top-[33px]' : 'top-0'} />
              <ImagingCompactList sections={filtered} />
            </div>
          );
        }

        if (section.type === 'text') {
          const items = section.textItems?.[0]?.items || [];
          const filtered = items.filter(item => {
            if (displayMode === 'abnormal' && (!item.abnormalStatus || item.abnormalStatus === 'normal')) return false;
            if (searchQuery) {
              const q = searchQuery.toLowerCase();
              return item.itemName.toLowerCase().includes(q) || (item.rawValue || '').toLowerCase().includes(q);
            }
            return true;
          });
          if (filtered.length === 0) return null;
          return (
            <div key={section.id} className="mb-1">
              <StickyHeader icon={<FileText className="w-3.5 h-3.5 text-slate-400" />} title={section.title} count={filtered.length} accent="slate" stickyOffset={hasMultiple ? 'top-[33px]' : 'top-0'} />
              <TextCompactList items={filtered} />
            </div>
          );
        }

        // Table
        const filtered = filterRows(section.rows);
        if (filtered.length === 0) return null;
        const abnormalCount = filtered.filter(r => r.worstStatus && r.worstStatus !== 'normal').length;
        return (
          <div key={section.id} className="mb-1">
            <StickyHeader title={section.title} count={filtered.length} abnormalCount={abnormalCount} accent="brand" stickyOffset={hasMultiple ? 'top-[33px]' : 'top-0'} />
            <MergedTable rows={filtered} examRecords={validRecords} searchQuery={searchQuery} hasMultiple={hasMultiple} />
          </div>
        );
      })}
    </div>
  );
}

// === Sub-components ===

function StickyHeader({ icon, title, count, abnormalCount, accent, stickyOffset }: {
  icon?: React.ReactNode; title: string; count: number; abnormalCount?: number; accent: string; stickyOffset?: string;
}) {
  const accentColors: Record<string, string> = {
    red: 'border-l-red-500 bg-red-50/90 dark:bg-red-950/40',
    orange: 'border-l-orange-500 bg-orange-50/90 dark:bg-orange-950/40',
    brand: 'border-l-brand bg-slate-50/90 dark:bg-slate-800/90',
    slate: 'border-l-slate-400 bg-slate-50/90 dark:bg-slate-800/90',
  };

  return (
    <div className={`sticky ${stickyOffset || 'top-0'} z-10 flex items-center justify-between px-4 py-2 border-l-[3px] ${accentColors[accent] || accentColors.brand} backdrop-blur-md border-b border-slate-100 dark:border-slate-800`}>
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-xs font-bold text-slate-700 dark:text-slate-200">{title}</span>
      </div>
      <div className="flex items-center gap-2">
        {abnormalCount != null && abnormalCount > 0 && (
          <span className="text-xs font-bold text-red-500 tabular-nums">{abnormalCount} 异常</span>
        )}
        <span className="text-xs text-slate-400 dark:text-slate-500 tabular-nums">{count} 项</span>
      </div>
    </div>
  );
}

function MergedTable({ rows, examRecords, searchQuery, hasMultiple }: {
  rows: MergedRow[]; examRecords: ExamRecord[]; searchQuery: string; hasMultiple: boolean;
}) {
  return (
    <table className="w-full">
      <tbody>
        {rows.map((row, idx) => {
          const isAbn = row.worstStatus && row.worstStatus !== 'normal';
          const isHighType = row.worstStatus === 'high' || row.worstStatus === 'positive' || row.worstStatus === 'critical';

          return (
            <tr
              key={`${row.itemCode}-${row.itemName}-${idx}`}
              className={`border-b border-slate-50 dark:border-slate-800/50 transition-colors duration-100 hover:bg-slate-100 dark:hover:bg-slate-800/60 ${
                isAbn ? (isHighType ? 'bg-red-50/40 dark:bg-red-950/15' : 'bg-blue-50/40 dark:bg-blue-950/15') : ''
              }`}
            >
              {/* Name */}
              <td className="pl-4 pr-2 py-1.5 w-[28%]">
                <div className="flex items-center gap-2">
                  <div className={`w-0.5 h-4 rounded-full shrink-0 ${isAbn ? (isHighType ? 'bg-red-400' : 'bg-blue-400') : 'bg-transparent'}`} />
                  <div>
                    <HighlightText text={row.itemName} query={searchQuery} className={`text-xs leading-tight ${isAbn ? 'font-semibold text-slate-900 dark:text-white' : 'text-slate-700 dark:text-slate-300'}`} />
                    {row.itemNameEn && <div className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">{row.itemNameEn}</div>}
                  </div>
                </div>
              </td>

              {/* Values — one column per exam */}
              {hasMultiple ? (
                examRecords.map((_, i) => {
                  const val = row.values[i];
                  if (!val) return <td key={i} className="px-2 py-1.5 text-center text-xs text-slate-300 dark:text-slate-600">—</td>;
                  const valAbn = val.abnormalStatus && val.abnormalStatus !== 'normal';
                  const valHigh = val.abnormalStatus === 'high' || val.abnormalStatus === 'positive' || val.abnormalStatus === 'critical';
                  return (
                    <td key={i} className="px-2 py-1.5 text-center">
                      <span className={`text-xs font-mono tabular-nums ${
                        valAbn ? (valHigh ? 'text-red-600 dark:text-red-400 font-bold' : 'text-blue-600 dark:text-blue-400 font-bold') : 'text-slate-800 dark:text-slate-200'
                      }`}>
                        {val.displayValue}
                      </span>
                      {val.unit && <span className="text-[10px] text-slate-400 ml-0.5">{val.unit}</span>}
                      {valAbn && (
                        <div className="mt-0.5">
                          <span className={`text-[10px] font-semibold ${valHigh ? 'text-red-500' : 'text-blue-500'}`}>{val.abnormalText}</span>
                        </div>
                      )}
                    </td>
                  );
                })
              ) : (
                // Single exam — original layout
                <td className="px-2 py-1.5 text-right w-[20%]">
                  {row.values[0] ? (
                    <>
                      <span className={`text-xs font-mono tabular-nums ${
                        isAbn ? (isHighType ? 'text-red-600 dark:text-red-400 font-bold' : 'text-blue-600 dark:text-blue-400 font-bold') : 'text-slate-800 dark:text-slate-200'
                      }`}>
                        {row.values[0].displayValue}
                      </span>
                      {row.values[0].unit && <span className="text-[10px] text-slate-400 ml-0.5">{row.values[0].unit}</span>}
                    </>
                  ) : <span className="text-xs text-slate-300">—</span>}
                </td>
              )}

              {/* Reference */}
              <td className="px-2 py-1.5 w-[14%]">
                <span className="text-[10px] text-slate-400 dark:text-slate-500 whitespace-nowrap truncate block max-w-[120px]" title={row.referenceRange}>
                  {row.referenceRange || '-'}
                </span>
              </td>
              {/* Status — worst */}
              <td className="pr-4 pl-2 py-1.5 w-[8%] text-right">
                <AbnormalBadge status={row.worstStatus} size="sm" />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function HighlightText({ text, query, className }: { text: string; query: string; className: string }) {
  if (!query) return <span className={className}>{text}</span>;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return <span className={className}>{text}</span>;
  return (
    <span className={className}>
      {text.substring(0, idx)}
      <mark className="bg-yellow-200 dark:bg-yellow-800/60 rounded-sm px-0.5">{text.substring(idx, idx + query.length)}</mark>
      {text.substring(idx + query.length)}
    </span>
  );
}

function ImagingCompactList({ sections }: { sections: ImagingSection[] }) {
  return (
    <div className="divide-y divide-slate-50 dark:divide-slate-800/50">
      {sections.map(section => (
        <div key={section.title} className={`px-4 py-2.5 ${section.hasAbnormal ? 'bg-orange-50/30 dark:bg-orange-950/10' : ''}`}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">{section.title}</span>
            <div className="flex items-center gap-2">
              {section.grading && (
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                  parseInt(section.grading.level) >= 3 ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-300' : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400'
                }`}>{section.grading.system} {section.grading.level}</span>
              )}
              {section.hasAbnormal && <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />}
            </div>
          </div>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed line-clamp-2">{section.findings.replace(/\r\n/g, ' ')}</p>
          {section.recommendation && <p className="text-[10px] text-brand font-medium mt-1">{section.recommendation}</p>}
        </div>
      ))}
    </div>
  );
}

function TextCompactList({ items }: { items: ParsedItem[] }) {
  return (
    <div className="divide-y divide-slate-50 dark:divide-slate-800/50">
      {items.map((item, idx) => (
        <div key={`${item.itemCode}-${idx}`} className="px-4 py-2">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">{item.itemName}</span>
            <AbnormalBadge status={item.abnormalStatus} text={item.abnormalText} size="sm" />
          </div>
          {item.rawValue && (
            <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed line-clamp-3">{item.rawValue.replace(/\r\n/g, ' ')}</p>
          )}
        </div>
      ))}
    </div>
  );
}
