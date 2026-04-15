export interface MetricData {
  name: string;
  unit: string;
  refRange: string;
  values: Record<string, number | string>;
  judgment: 'high' | 'low' | 'normal';
  trend: string;
}

export interface Message {
  role: 'user' | 'ai';
  content: string;
}

export interface AIReportComparisonReportViewProps {
  customer: any;
  onBack: () => void;
  isDarkMode: boolean;
  setIsDarkMode: (value: boolean) => void;
}
