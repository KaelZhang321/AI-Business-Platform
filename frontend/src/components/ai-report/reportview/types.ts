/** 指标数据（报告对比视图中单个检验指标） */
export interface MetricData {
  /** 指标名称 */
  name: string;
  /** 计量单位 */
  unit: string;
  /** 参考范围 */
  refRange: string;
  /** 各期数值（键为日期/期次，值为数值或文本） */
  values: Record<string, number | string>;
  /** AI 判断：偏高 / 偏低 / 正常 */
  judgment: 'high' | 'low' | 'normal';
  /** 趋势描述 */
  trend: string;
}

/** 报告对比视图中的聊天消息 */
export interface Message {
  /** 角色：user / ai */
  role: 'user' | 'ai';
  /** 消息内容 */
  content: string;
}

/** AI 报告对比视图组件属性 */
export interface AIReportComparisonReportViewProps {
  /** 当前客户数据 */
  customer: any;
  /** 返回上一页回调 */
  onBack: () => void;
  /** 是否暗色模式 */
  isDarkMode: boolean;
  /** 切换暗色模式 */
  setIsDarkMode: (value: boolean) => void;
}

