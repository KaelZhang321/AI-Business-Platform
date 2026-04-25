import type {
  RawReportResponse, RawItem, ParsedItem, AbnormalStatus,
  ClinicalGroup, ClinicalSubGroup, ConclusionItem, ImagingSection,
  HealthReportData,
} from '../../types/healthReport';

// ============================================================
// 1. Value Parsing — handles all observed formats in the data
// ============================================================

/** Extract numeric value from mixed strings like "7.4kg  (7.7-9.4)   偏低" */
function extractNumeric(raw: string): number | null {
  // Try leading number: "5.65", "19791", "0.07", "<0.0250", "+4.9kg", "-5.0kg"
  const m = raw.match(/^[<>]?\s*([+-]?\d+\.?\d*)/);
  return m ? parseFloat(m[1]) : null;
}

/** Extract unit from value like "28.2kg" or "1198kcal" */
function extractUnit(raw: string, fallbackUnit: string): string {
  if (fallbackUnit && fallbackUnit.trim()) return fallbackUnit.trim();
  const m = raw.match(/^\d+\.?\d*\s*([a-zA-Zμ%/]+)/);
  return m ? m[1] : '';
}

/** Extract reference range from value like "31.8%(18.0-28.0)" or standalone ref */
function parseReferenceRange(rawRef: string | null, rawValue: string | null): { display: string; min: number | null; max: number | null } {
  const empty = { display: '', min: null, max: null };

  // Try rawRef first (化验室 items have structured refs like "0.0-20.0")
  if (rawRef && rawRef.trim() && rawRef.trim() !== '~' && rawRef.trim() !== ' ~ ') {
    const rangeMatch = rawRef.match(/([\d.]+)\s*[-–~]\s*([\d.]+)/);
    if (rangeMatch) {
      return { display: rawRef.trim(), min: parseFloat(rangeMatch[1]), max: parseFloat(rangeMatch[2]) };
    }
    return { display: rawRef.trim(), min: null, max: null };
  }

  // Fallback: extract from resultValue like "7.4kg  (7.7-9.4)   偏低"
  if (rawValue) {
    const m = rawValue.match(/\((\d+\.?\d*)\s*[-–~]\s*(\d+\.?\d*)\)/);
    if (m) {
      return { display: `${m[1]}-${m[2]}`, min: parseFloat(m[1]), max: parseFloat(m[2]) };
    }
  }

  return empty;
}

/** Determine abnormal status from abnormalFlag + text cues in value */
function determineAbnormalStatus(item: RawItem): { status: AbnormalStatus; text: string } {
  const val = item.resultValue || '';
  const flag = item.abnormalFlag;

  // abnormalFlag: "0" = normal, "1" = low, "2" = high, null = unknown
  if (flag === '2') {
    // Check if it's a positive result (qualitative)
    if (/阳性|Ⅲ°|Ⅳ°/.test(val)) return { status: 'positive', text: '阳性' };
    return { status: 'high', text: '偏高' };
  }
  if (flag === '1') return { status: 'low', text: '偏低' };
  if (flag === '0') return { status: 'normal', text: '' };

  // No flag — check text cues in resultValue
  if (/偏高|升高|↑/.test(val)) return { status: 'high', text: '偏高' };
  if (/偏低|降低|↓/.test(val)) return { status: 'low', text: '偏低' };
  if (/阳性|\(\+\)/.test(val)) return { status: 'positive', text: '阳性' };

  return { status: 'normal', text: '' };
}

/** Clean display value: strip embedded ranges and status text */
function cleanDisplayValue(raw: string): string {
  // Remove trailing status words
  let v = raw.replace(/\s*(偏高|偏低|正常|升高|降低)\s*$/g, '').trim();
  // Remove embedded parenthetical ranges like "(7.7-9.4)"
  v = v.replace(/\s*\(\d+\.?\d*\s*[-–~]\s*\d+\.?\d*\)\s*/g, '').trim();
  // Remove "（阴性 -）" patterns
  v = v.replace(/（[^）]*）/g, '').trim();
  return v || raw;
}

function parseItem(item: RawItem, deptName: string, deptCode: string): ParsedItem {
  const raw = item.resultValue;
  const { status, text } = determineAbnormalStatus(item);
  const ref = parseReferenceRange(item.referenceRange, raw);

  return {
    itemCode: item.itemCode,
    itemName: item.itemName.replace(/^★/, '').trim(),
    itemNameEn: item.itemNameEn || '',
    rawValue: raw,
    displayValue: raw ? cleanDisplayValue(raw) : '-',
    numericValue: raw ? extractNumeric(raw) : null,
    unit: raw ? extractUnit(raw, item.unit) : item.unit,
    referenceRange: ref.display,
    refMin: ref.min,
    refMax: ref.max,
    abnormalStatus: status,
    abnormalText: text,
    majorItemCode: item.majorItemCode,
    majorItemName: item.majorItemName?.replace(/^H-/, '') || null,
    originalDepartment: deptName,
    originalDepartmentCode: deptCode,
  };
}

// ============================================================
// 2. Deduplication — many items appear twice in the raw data
// ============================================================

function deduplicateItems(items: ParsedItem[]): ParsedItem[] {
  const seen = new Map<string, ParsedItem>();
  for (const item of items) {
    // Use composite key: code + name + value
    const key = `${item.itemCode}|${item.itemName}|${item.rawValue}`;
    if (!seen.has(key)) {
      seen.set(key, item);
    }
  }
  return Array.from(seen.values());
}

// ============================================================
// 3. Clinical grouping — map raw departments to clinical groups
// ============================================================

// Map departmentCode to clinical group id
const DEPT_TO_GROUP: Record<string, string> = {
  'YB': 'vitals',        // 一般检查
  'ER': 'vitals',        // 人体成份
  'HY': 'lab',           // 化验室
  'US': 'imaging',       // 彩超室
  'FK': 'specialty',     // 妇科
  'EY': 'specialty',     // 妇科总检室
  'EZ': 'specialty',     // TS检查
  'WK': 'specialty',     // 外科
  'WZ': 'health',        // 健康问诊
};

// Lab sub-group mapping by majorItemName prefix
const LAB_SUBGROUPS: [RegExp, string, string][] = [
  [/血常规/, 'hematology', '血液学'],
  [/血脂/, 'lipid', '血脂代谢'],
  [/肝功/, 'liver', '肝功能'],
  [/肾功/, 'renal', '肾功能'],
  [/血糖|糖化/, 'glucose', '糖代谢'],
  [/女性激素/, 'hormone', '内分泌-性激素'],
  [/甲功|甲状腺/, 'thyroid', '内分泌-甲状腺'],
  [/营养元素/, 'nutrition', '营养代谢'],
  [/肿瘤标志物/, 'tumor', '肿瘤标志物'],
  [/凝血/, 'coagulation', '凝血功能'],
  [/尿常规/, 'urinalysis', '尿液分析'],
  [/尿微量白蛋白/, 'urine-protein', '尿蛋白'],
  [/白带/, 'vaginal', '阴道分泌物'],
  [/细菌性阴道病/, 'bv', '细菌性阴道病检测'],
  [/HPV|人乳头瘤/, 'hpv', 'HPV检测'],
  [/食物不耐受/, 'food-intolerance', '食物不耐受'],
  [/风湿/, 'rheumatology', '风湿免疫'],
  [/免疫球蛋白/, 'immunoglobulin', '免疫球蛋白'],
  [/血型/, 'blood-type', '血型鉴定'],
  [/梅毒/, 'syphilis', '梅毒检测'],
  [/艾滋/, 'hiv', 'HIV检测'],
  [/丙型肝炎/, 'hcv', '丙肝检测'],
  [/D二聚体/, 'd-dimer', 'D-二聚体'],
  [/巨细胞/, 'cmv', '巨细胞病毒'],
  [/抗缪勒管/, 'amh', '卵巢储备功能'],
  [/C13/, 'c13', '幽门螺杆菌检测'],
  [/抗环瓜氨酸/, 'anti-ccp', '抗CCP抗体'],
];

function getLabSubGroupId(majorItemName: string | null): { id: string; name: string } {
  if (!majorItemName) return { id: 'other-lab', name: '其他检验' };
  const clean = majorItemName.replace(/^H-/, '');
  for (const [re, id, name] of LAB_SUBGROUPS) {
    if (re.test(clean)) return { id, name };
  }
  return { id: 'other-lab', name: '其他检验' };
}

// ============================================================
// 4. Imaging section parser
// ============================================================

function parseImagingSections(items: ParsedItem[]): ImagingSection[] {
  // Find the "检查所见" (conclusions) and "检查描述" (descriptions)
  const conclusionItem = items.find(i => i.itemName === '检查所见');
  const descriptionItem = items.find(i => i.itemName === '检查描述');

  const conclusionText = conclusionItem?.rawValue || '';
  const descriptionText = descriptionItem?.rawValue || '';

  // Split by "H-" prefix sections
  const sections: ImagingSection[] = [];
  const sectionRegex = /H-([^\r\n:：]+)[：:]?\s*\r?\n([\s\S]*?)(?=H-|$)/g;

  let match: RegExpExecArray | null;
  while ((match = sectionRegex.exec(conclusionText)) !== null) {
    const title = match[1].trim();
    const findings = match[2].trim();

    // Find corresponding description
    const descRegex = new RegExp(`H-${title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[：:]?\\s*\\r?\\n([\\s\\S]*?)(?=H-|$)`);
    const descMatch = descRegex.exec(descriptionText);
    const description = descMatch ? descMatch[1].trim() : '';

    // Extract grading (TI-RADS, BI-RADS)
    let grading: { system: string; level: string } | undefined;
    const tiRadsMatch = findings.match(/TI-RADS\s*(\d+)级/);
    const biRadsMatch = findings.match(/BI-RADS\s*(\d+)类/);
    if (tiRadsMatch) grading = { system: 'TI-RADS', level: tiRadsMatch[1] + '级' };
    if (biRadsMatch) grading = { system: 'BI-RADS', level: biRadsMatch[1] + '类' };

    // Extract recommendations
    const recMatch = findings.match(/建议[^，。\r\n]*/g);
    const recommendation = recMatch ? recMatch.join('；') : undefined;

    // Determine if abnormal (anything besides "未见明显异常")
    const hasAbnormal = !/^未见明显异常/.test(findings) && findings.length > 0;

    sections.push({ title, findings, description, grading, recommendation, hasAbnormal });
  }

  return sections;
}

// ============================================================
// 5. Conclusion parser
// ============================================================

const CRITICAL_KEYWORDS = ['结石', '肌瘤', '阴道病', '高胆固醇'];
const WARNING_KEYWORDS = ['结节', '囊肿', '息肉', '增厚', '反流', '升高', '降低', 'RADS'];

function parseConclusions(raw: string): ConclusionItem[] {
  const lines = raw.split(/\r?\n/).filter(l => l.trim());
  return lines.map((line, idx) => {
    const textMatch = line.match(/【\d+\.\s*(.+?)】/);
    const text = textMatch ? textMatch[1] : line.replace(/【|】/g, '').trim();

    let severity: ConclusionItem['severity'] = 'info';
    if (CRITICAL_KEYWORDS.some(k => text.includes(k))) severity = 'critical';
    else if (WARNING_KEYWORDS.some(k => text.includes(k))) severity = 'warning';

    return { index: idx + 1, text, severity };
  }).filter(c => c.text.length > 0);
}

// ============================================================
// 6. Health questionnaire filter — skip low-value binary fields
// ============================================================

function isHealthQuestionnaireNoise(item: ParsedItem): boolean {
  // 健康问诊 items with value "0" are just checkboxes (no disease history)
  if (item.originalDepartmentCode === 'WZ') {
    if (item.rawValue === '0' || item.rawValue === null) return true;
    // Keep "小结" items that have meaningful text
    if (item.itemName === '小结' && item.rawValue && item.rawValue !== '无') return false;
    if (item.rawValue === '无') return true;
  }
  return false;
}

// ============================================================
// 7. Main mapper
// ============================================================

export function mapReportData(raw: RawReportResponse): HealthReportData {
  const data = raw.data;

  // Parse all items from all departments
  const allParsed: ParsedItem[] = [];
  for (const dept of data.departments) {
    for (const item of dept.items) {
      allParsed.push(parseItem(item, dept.departmentName, dept.departmentCode));
    }
  }

  // Deduplicate
  const deduped = deduplicateItems(allParsed);

  // Filter out null/empty values and noise
  const meaningful = deduped.filter(i => {
    if (i.rawValue === null && i.itemName !== '检查描述') return false;
    if (isHealthQuestionnaireNoise(i)) return false;
    return true;
  });

  // Group by clinical category
  const groupMap = new Map<string, ParsedItem[]>();
  for (const item of meaningful) {
    const groupId = DEPT_TO_GROUP[item.originalDepartmentCode] || 'health';
    const existing = groupMap.get(groupId) || [];
    existing.push(item);
    groupMap.set(groupId, existing);
  }

  // Build clinical groups
  const clinicalGroups: ClinicalGroup[] = [];

  // --- Vitals (基础体征) ---
  const vitalsItems = groupMap.get('vitals') || [];
  if (vitalsItems.length > 0) {
    const bodyComp = vitalsItems.filter(i => i.originalDepartmentCode === 'ER');
    const generalExam = vitalsItems.filter(i => i.originalDepartmentCode === 'YB');
    const subGroups: ClinicalSubGroup[] = [];
    if (generalExam.length) {
      subGroups.push({
        id: 'general-exam', name: '一般检查',
        items: generalExam,
        abnormalCount: generalExam.filter(i => i.abnormalStatus && i.abnormalStatus !== 'normal').length,
        totalCount: generalExam.length,
      });
    }
    if (bodyComp.length) {
      subGroups.push({
        id: 'body-composition', name: '人体成份',
        items: bodyComp,
        abnormalCount: bodyComp.filter(i => i.abnormalStatus && i.abnormalStatus !== 'normal').length,
        totalCount: bodyComp.length,
      });
    }
    clinicalGroups.push({
      id: 'vitals', name: '基础体征', icon: 'Activity',
      subGroups, type: 'table',
      abnormalCount: subGroups.reduce((s, g) => s + g.abnormalCount, 0),
      totalCount: subGroups.reduce((s, g) => s + g.totalCount, 0),
    });
  }

  // --- Lab (实验室检验) ---
  const labItems = groupMap.get('lab') || [];
  if (labItems.length > 0) {
    const labSubMap = new Map<string, ParsedItem[]>();
    const labSubNames = new Map<string, string>();
    for (const item of labItems) {
      const { id, name } = getLabSubGroupId(item.majorItemName);
      const arr = labSubMap.get(id) || [];
      arr.push(item);
      labSubMap.set(id, arr);
      labSubNames.set(id, name);
    }
    const subGroups: ClinicalSubGroup[] = Array.from(labSubMap.entries()).map(([id, items]) => ({
      id, name: labSubNames.get(id) || id,
      items,
      abnormalCount: items.filter(i => i.abnormalStatus && i.abnormalStatus !== 'normal').length,
      totalCount: items.length,
    }));
    clinicalGroups.push({
      id: 'lab', name: '实验室检验', icon: 'TestTubes',
      subGroups, type: 'table',
      abnormalCount: subGroups.reduce((s, g) => s + g.abnormalCount, 0),
      totalCount: subGroups.reduce((s, g) => s + g.totalCount, 0),
    });
  }

  // --- Imaging (影像检查) ---
  const imagingItems = groupMap.get('imaging') || [];
  const imagingSections = parseImagingSections(imagingItems);
  if (imagingSections.length > 0) {
    const subGroups: ClinicalSubGroup[] = imagingSections.map(s => ({
      id: s.title.replace(/\s+/g, '-'), name: s.title,
      items: [], abnormalCount: s.hasAbnormal ? 1 : 0, totalCount: 1,
    }));
    clinicalGroups.push({
      id: 'imaging', name: '影像检查', icon: 'ScanLine',
      subGroups, type: 'imaging',
      abnormalCount: imagingSections.filter(s => s.hasAbnormal).length,
      totalCount: imagingSections.length,
    });
  }

  // --- Specialty (专科检查) ---
  const specialtyItems = groupMap.get('specialty') || [];
  if (specialtyItems.length > 0) {
    const deptSubMap = new Map<string, ParsedItem[]>();
    const deptSubNames = new Map<string, string>();
    for (const item of specialtyItems) {
      const key = item.originalDepartmentCode;
      const arr = deptSubMap.get(key) || [];
      arr.push(item);
      deptSubMap.set(key, arr);
      deptSubNames.set(key, item.originalDepartment);
    }
    const subGroups: ClinicalSubGroup[] = Array.from(deptSubMap.entries()).map(([id, items]) => ({
      id, name: deptSubNames.get(id) || id,
      items,
      abnormalCount: items.filter(i => i.abnormalStatus && i.abnormalStatus !== 'normal').length,
      totalCount: items.length,
    }));
    clinicalGroups.push({
      id: 'specialty', name: '专科检查', icon: 'Stethoscope',
      subGroups, type: 'text',
      abnormalCount: subGroups.reduce((s, g) => s + g.abnormalCount, 0),
      totalCount: subGroups.reduce((s, g) => s + g.totalCount, 0),
    });
  }

  // --- Health (健康评估) ---
  const healthItems = groupMap.get('health') || [];
  if (healthItems.length > 0) {
    const subGroups: ClinicalSubGroup[] = [{
      id: 'health-consult', name: '健康问诊',
      items: healthItems,
      abnormalCount: healthItems.filter(i => i.abnormalStatus && i.abnormalStatus !== 'normal').length,
      totalCount: healthItems.length,
    }];
    clinicalGroups.push({
      id: 'health', name: '健康评估', icon: 'HeartPulse',
      subGroups, type: 'text',
      abnormalCount: subGroups.reduce((s, g) => s + g.abnormalCount, 0),
      totalCount: subGroups.reduce((s, g) => s + g.totalCount, 0),
    });
  }

  // Conclusions
  const conclusions = parseConclusions(data.finalConclusion);

  // Totals
  const totalItems = meaningful.length;
  const totalAbnormal = meaningful.filter(i => i.abnormalStatus && i.abnormalStatus !== 'normal').length;

  return {
    studyId: data.studyId,
    examTime: data.examTime,
    packageName: data.packageName,
    abnormalCount: data.abnormalCount,
    conclusions,
    abnormalSummary: data.abnormalSummary,
    clinicalGroups,
    imagingSections,
    totalItems,
    totalAbnormal,
  };
}
