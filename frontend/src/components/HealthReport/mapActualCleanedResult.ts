import type {
  AbnormalStatus,
  ClinicalGroup,
  ClinicalSubGroup,
  ConclusionItem,
  HealthReportData,
  ImagingSection,
  ParsedItem,
} from '../../types/healthReport';
import type {
  PatientExamCleanedResultData,
  PatientExamCleanedResultResponse,
  PatientExamIndicator,
} from '../../types/patientExamCleanedResult';

const GROUP_META: Record<string, { id: string; name: string; icon: string; type: ClinicalGroup['type'] }> = {
  一般检查: { id: 'vitals-general', name: '一般检查', icon: 'Activity', type: 'table' },
  人体成分: { id: 'vitals-body-composition', name: '人体成分', icon: 'Activity', type: 'table' },
  妇科: { id: 'specialty-gynecology', name: '妇科', icon: 'Stethoscope', type: 'text' },
  内科: { id: 'specialty-internal', name: '内科', icon: 'Stethoscope', type: 'text' },
  外科: { id: 'specialty-surgery', name: '外科', icon: 'Stethoscope', type: 'text' },
  健康问诊: { id: 'health-consult', name: '健康问诊', icon: 'HeartPulse', type: 'text' },
};

function slugify(input: string) {
  return input
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^\w\u4e00-\u9fa5-]/g, '');
}

function normalizeCategory(category: string | null, standardName: string): string {
  if (category && category.trim()) return category.trim();
  if (standardName === '检查所见' || standardName === '检查描述') return '影像检查';
  return '未分类';
}

function parseNumber(input: string | number | null): number | null {
  if (input === null || input === undefined || input === '') return null;
  const value = typeof input === 'number' ? input : parseFloat(String(input));
  return Number.isFinite(value) ? value : null;
}

function extractNumeric(raw: string | null): number | null {
  if (!raw) return null;
  const match = raw.match(/^[<>]?\s*([+-]?\d+\.?\d*)/);
  return match ? parseFloat(match[1]) : null;
}

function cleanDisplayValue(raw: string | null): string {
  if (!raw) return '-';
  return raw.replace(/\r\n/g, '\n').trim();
}

function resolveStatus(indicator: PatientExamIndicator): { status: AbnormalStatus; text: string } {
  const value = indicator.value || '';
  if (indicator.is_abnormal) {
    if (/阳性|Ⅲ°|Ⅳ°/.test(value)) return { status: 'positive', text: '异常' };
    if (indicator.abnormal_direction === 'high') return { status: 'high', text: '偏高' };
    if (indicator.abnormal_direction === 'low') return { status: 'low', text: '偏低' };
    return { status: 'critical', text: '异常' };
  }
  if (/阳性/.test(value)) return { status: 'positive', text: '阳性' };
  if (/偏高|升高|↑/.test(value)) return { status: 'high', text: '偏高' };
  if (/偏低|降低|↓/.test(value)) return { status: 'low', text: '偏低' };
  return { status: 'normal', text: '' };
}

function parseIndicator(indicator: PatientExamIndicator): ParsedItem {
  const { status, text } = resolveStatus(indicator);
  const category = normalizeCategory(indicator.category, indicator.standard_name);

  return {
    itemCode: indicator.standard_code,
    itemName: indicator.standard_name,
    itemNameEn: '',
    rawValue: indicator.value,
    displayValue: cleanDisplayValue(indicator.value),
    numericValue: extractNumeric(indicator.value),
    unit: indicator.unit?.trim() || '',
    referenceRange:
      indicator.reference_range?.trim() === '~' || indicator.reference_range?.trim() === ' ~ '
        ? ''
        : indicator.reference_range || '',
    refMin: parseNumber(indicator.ref_min),
    refMax: parseNumber(indicator.ref_max),
    abnormalStatus: status,
    abnormalText: text,
    majorItemCode: null,
    majorItemName: category,
    originalDepartment: category,
    originalDepartmentCode: slugify(category),
  };
}

function deduplicate(items: ParsedItem[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = `${item.originalDepartment}|${item.itemCode}|${item.itemName}|${item.rawValue || ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function inferGroupType(category: string, items: ParsedItem[]): ClinicalGroup['type'] {
  if (category === '影像检查') return 'imaging';
  if (category === '健康问诊' || category === '妇科' || category === '内科' || category === '外科') return 'text';
  const textHeavy = items.filter((item) => (item.rawValue || '').length > 40).length;
  return textHeavy > Math.max(2, items.length / 2) ? 'text' : 'table';
}

function inferIcon(category: string, type: ClinicalGroup['type']) {
  if (type === 'imaging') return 'ScanLine';
  if (type === 'text' && category === '健康问诊') return 'HeartPulse';
  if (type === 'text') return 'Stethoscope';
  return 'TestTubes';
}

function buildGroups(items: ParsedItem[]): ClinicalGroup[] {
  const byCategory = new Map<string, ParsedItem[]>();
  for (const item of items) {
    const key = item.originalDepartment;
    const list = byCategory.get(key) || [];
    list.push(item);
    byCategory.set(key, list);
  }

  return Array.from(byCategory.entries()).map(([category, groupItems]) => {
    const explicitMeta = GROUP_META[category];
    const type = explicitMeta?.type || inferGroupType(category, groupItems);
    const subGroup: ClinicalSubGroup = {
      id: slugify(category),
      name: category,
      items: groupItems,
      abnormalCount: groupItems.filter((item) => item.abnormalStatus && item.abnormalStatus !== 'normal').length,
      totalCount: groupItems.length,
    };

    return {
      id: explicitMeta?.id || slugify(category),
      name: explicitMeta?.name || category,
      icon: explicitMeta?.icon || inferIcon(category, type),
      subGroups: [subGroup],
      abnormalCount: subGroup.abnormalCount,
      totalCount: subGroup.totalCount,
      type,
    };
  });
}

function buildImagingSections(items: ParsedItem[]): ImagingSection[] {
  const text = items
    .filter((item) => item.itemName === '检查所见')
    .map((item) => item.rawValue || '')
    .join('\n');

  if (!text) return [];

  const sections: ImagingSection[] = [];
  const sectionRegex = /H-([^\r\n:：]+)[：:]?\s*\r?\n([\s\S]*?)(?=H-|$)/g;
  let match: RegExpExecArray | null;

  while ((match = sectionRegex.exec(text)) !== null) {
    const title = match[1].trim();
    const findings = match[2].trim();
    const gradingMatch = findings.match(/(TI-RADS|BI-RADS)\s*([0-9]+[级类])/);
    const recommendationMatch = findings.match(/建议[^\r\n]*/g);

    sections.push({
      title,
      findings,
      description: '',
      grading: gradingMatch ? { system: gradingMatch[1], level: gradingMatch[2] } : undefined,
      recommendation: recommendationMatch ? recommendationMatch.join('；') : undefined,
      hasAbnormal: !/未见明显异常/.test(findings),
    });
  }

  return sections;
}

function buildConclusions(items: ParsedItem[]): ConclusionItem[] {
  const abnormalItems = items
    .filter((item) => item.abnormalStatus && item.abnormalStatus !== 'normal')
    .slice(0, 20)
    .map((item, index) => ({
      index: index + 1,
      text: `${item.originalDepartment} · ${item.itemName}${item.rawValue ? `：${item.rawValue}` : ''}`,
      severity:
        item.abnormalStatus === 'critical' || item.abnormalStatus === 'positive'
          ? ('critical' as const)
          : ('warning' as const),
    }));

  if (abnormalItems.length > 0) return abnormalItems;

  return items
    .filter((item) => ['检查所见', '小结', '妇科总检'].includes(item.itemName) && item.rawValue)
    .slice(0, 12)
    .map((item, index) => ({
      index: index + 1,
      text: `${item.originalDepartment} · ${item.rawValue}`,
      severity: 'info' as const,
    }));
}

function buildAbnormalSummary(groups: ClinicalGroup[]): string {
  return groups
    .filter((group) => group.abnormalCount > 0)
    .map((group) => {
      const abnormalNames = group.subGroups[0]?.items
        .filter((item) => item.abnormalStatus && item.abnormalStatus !== 'normal')
        .slice(0, 8)
        .map((item) => item.itemName)
        .join('、');
      return abnormalNames ? `${group.name}：${abnormalNames}` : '';
    })
    .filter(Boolean)
    .join('\n');
}

export function mapActualCleanedResult(
  input: PatientExamCleanedResultResponse | PatientExamCleanedResultData,
): HealthReportData {
  const data = 'data' in input ? input.data : input;

  const parsed = deduplicate(data.indicators.map(parseIndicator)).filter(
    (item) => item.rawValue !== null || item.itemName === '检查描述',
  );
  const clinicalGroups = buildGroups(parsed).filter((group) => group.name !== '影像检查');
  const imagingItems = parsed.filter((item) => item.originalDepartment === '影像检查');
  const imagingSections = buildImagingSections(imagingItems);

  if (imagingSections.length > 0) {
    clinicalGroups.splice(2, 0, {
      id: 'imaging',
      name: '影像检查',
      icon: 'ScanLine',
      subGroups: imagingSections.map((section) => ({
        id: slugify(section.title),
        name: section.title,
        items: [],
        abnormalCount: section.hasAbnormal ? 1 : 0,
        totalCount: 1,
      })),
      abnormalCount: imagingSections.filter((section) => section.hasAbnormal).length,
      totalCount: imagingSections.length,
      type: 'imaging',
    });
  }

  const conclusions = buildConclusions(parsed);
  const totalAbnormal = parsed.filter((item) => item.abnormalStatus && item.abnormalStatus !== 'normal').length;

  return {
    studyId: data.study_id,
    examTime: data.exam_time,
    packageName: data.package_name,
    patientName: data.patient_name,
    gender: data.gender,
    abnormalCount: data.summary.abnormal_count,
    conclusions,
    abnormalSummary: buildAbnormalSummary(clinicalGroups),
    clinicalGroups,
    imagingSections,
    totalItems: data.summary.total_indicators,
    totalAbnormal: Math.max(totalAbnormal, data.summary.abnormal_count),
  };
}
