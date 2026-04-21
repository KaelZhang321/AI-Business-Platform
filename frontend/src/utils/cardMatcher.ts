export const getCardIdFromQuery = (query: string): string | null => {
  if (query.includes('资产') || query.includes('asset')) return 'asset-info';
  if (query.includes('身份') || query.includes('联系')) return 'identity-contact';
  if (query.includes('基础数据') || query.includes('basic health')) return 'basic-health-data';
  if (query.includes('医疗史') || query.includes('健康状况')) return 'health-status-medical-history';
  if (query.includes('体检')) return 'physical-exam-status';
  if (query.includes('生活方式') || query.includes('习惯')) return 'lifestyle-habits';
  if (query.includes('心理') || query.includes('情绪')) return 'psychology-emotion';
  if (query.includes('喜好') || query.includes('优势')) return 'personal-preferences';
  if (query.includes('目标') || query.includes('痛点')) return 'health-goals';
  if (query.includes('消费能力') || query.includes('背景')) return 'consumption-ability';
  if (query.includes('客户关系') || query.includes('服务记录')) return 'customer-relations';
  if (query.includes('教育铺垫')) return 'education-records';
  if (query.includes('注意事项') || query.includes('precautions')) return 'precautions';
  if (query.includes('综合分析') || query.includes('咨询记录')) return 'consultation-records';
  if (query.includes('备注') || query.includes('remarks')) return 'remarks';
  if (query.includes('负责人') || query.includes('执行日期')) return 'execution-date';
  
  if (query.includes('卡片')) return 'asset-info'; // default to asset-info for demo
  
  return null;
};
