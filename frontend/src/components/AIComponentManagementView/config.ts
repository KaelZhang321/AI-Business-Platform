import type { CardConfig, LayoutMap } from './types';

export const initialCards: CardConfig[] = [
  // { id: 'asset-info', title: '客户资产概览', type: 'asset-info' },
  { id: 'identity-contact', title: '身份与联系信息', type: 'identity-contact' },
  { id: 'basic-health-data', title: '健康基础数据', type: 'basic-health-data' },
  { id: 'health-status-medical-history', title: '健康状况与医疗史', type: 'health-status-medical-history' },
  { id: 'physical-exam-status', title: '体检情况', type: 'physical-exam-status' },
  { id: 'lifestyle-habits', title: '生活方式与习惯', type: 'lifestyle-habits' },
  { id: 'psychology-emotion', title: '心理与情绪', type: 'psychology-emotion' },
  { id: 'personal-preferences', title: '个人喜好与优势', type: 'personal-preferences' },
  { id: 'health-goals', title: '健康目标与核心痛点', type: 'health-goals' },
  { id: 'consumption-ability', title: '消费能力与背景', type: 'consumption-ability' },
  { id: 'customer-relations', title: '客户关系与服务记录', type: 'customer-relations' },
  { id: 'education-records', title: '教育铺垫记录', type: 'education-records' },
  { id: 'precautions', title: '注意事项', type: 'precautions' },
  { id: 'consultation-records', title: '综合分析及咨询记录', type: 'consultation-records' },
  { id: 'remarks', title: '备注', type: 'remarks' },
  { id: 'execution-date', title: '负责人及执行日期', type: 'execution-date' },
];

export const initialLayouts: LayoutMap = {
  doctor: ['identity-contact', 'basic-health-data', 'health-status-medical-history', 'physical-exam-status', 'consultation-records'],
  consultant: ['identity-contact', 'asset-info', 'health-goals', 'psychology-emotion', 'customer-relations'],
  sales: ['identity-contact', 'asset-info', 'consumption-ability', 'education-records', 'precautions'],
};

export const initialCategories = ['客户基本信息', '团队信息', '资产与服务'];
