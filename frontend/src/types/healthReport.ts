// === Raw API types (matches lxl-2512125012.txt JSON structure) ===

export interface RawReportResponse {
  code: number;
  message: string;
  data: RawReportData;
}

export interface RawReportData {
  studyId: string;
  orderCode: string | null;
  examTime: string;
  packageCode: string;
  packageName: string;
  abnormalSummary: string;
  finalConclusion: string;
  abnormalCount: number;
  departments: RawDepartment[];
}

export interface RawDepartment {
  departmentCode: string;
  departmentName: string;
  sourceTable: string;
  items: RawItem[];
}

export interface RawItem {
  majorItemCode: string | null;
  majorItemName: string | null;
  itemCode: string;
  itemName: string;
  itemNameEn: string;
  resultValue: string | null;
  unit: string;
  referenceRange: string | null;
  abnormalFlag: string | null;
}

// === Parsed / display types ===

export type AbnormalStatus = 'high' | 'low' | 'positive' | 'normal' | 'critical' | null;

export interface ParsedItem {
  itemCode: string;
  itemName: string;
  itemNameEn: string;
  rawValue: string | null;        // original resultValue, preserved for completeness
  displayValue: string;            // cleaned display value
  numericValue: number | null;     // extracted number if applicable
  unit: string;
  referenceRange: string;          // display string for reference
  refMin: number | null;
  refMax: number | null;
  abnormalStatus: AbnormalStatus;
  abnormalText: string;            // "偏高", "偏低", "阳性" etc.
  majorItemCode: string | null;
  majorItemName: string | null;
  originalDepartment: string;
  originalDepartmentCode: string;
}

export interface ClinicalSubGroup {
  id: string;
  name: string;
  items: ParsedItem[];
  abnormalCount: number;
  totalCount: number;
}

export interface ClinicalGroup {
  id: string;
  name: string;
  icon: string;                    // lucide icon name
  subGroups: ClinicalSubGroup[];
  abnormalCount: number;
  totalCount: number;
  type: 'overview' | 'table' | 'imaging' | 'text';
}

export interface ConclusionItem {
  index: number;
  text: string;
  severity: 'critical' | 'warning' | 'info';
}

export interface ImagingSection {
  title: string;
  findings: string;
  description: string;
  grading?: { system: string; level: string };
  recommendation?: string;
  hasAbnormal: boolean;
}

export interface HealthReportData {
  studyId: string;
  examTime: string;
  packageName: string;
  abnormalCount: number;
  conclusions: ConclusionItem[];
  abnormalSummary: string;
  clinicalGroups: ClinicalGroup[];
  imagingSections: ImagingSection[];
  totalItems: number;
  totalAbnormal: number;
}

export interface ExamRecord {
  id: string;                // studyId or derived unique key
  examTime: string;          // "2025-12-12 08:01:20"
  examDate: string;          // "2025-12-12" (for display)
  year: string;              // "2025"
  packageName: string;
  reportData: HealthReportData;
}

export type DisplayMode = 'all' | 'abnormal';
