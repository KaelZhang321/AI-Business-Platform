/**
 * 卡片匹配工具：根据用户输入的查询关键词，匹配出对应的卡片 ID。
 * 用于 AI 助手对话场景，根据问题中的关键字自动定位到相关客户信息卡片。
 * @param query - 用户输入的查询文本
 * @returns 匹配到的卡片 ID，未匹配时返回 null
 */
export const getCardIdFromQuery = (query: string): string | null => {
  // 匹配「资产信息」卡片
  if (query.includes('资产') || query.includes('asset')) return 'asset-info';
  // 匹配「身份与联系方式」卡片
  if (query.includes('身份') || query.includes('联系')) return 'identity-contact';
  // 匹配「基础健康数据」卡片
  if (query.includes('基础数据') || query.includes('basic health')) return 'basic-health-data';
  // 匹配「健康状况与医疗史」卡片
  if (query.includes('医疗史') || query.includes('健康状况')) return 'health-status-medical-history';
  // 匹配「体检现状」卡片
  if (query.includes('体检')) return 'physical-exam-status';
  // 匹配「生活方式与习惯」卡片
  if (query.includes('生活方式') || query.includes('习惯')) return 'lifestyle-habits';
  // 匹配「心理与情绪」卡片
  if (query.includes('心理') || query.includes('情绪')) return 'psychology-emotion';
  // 匹配「个人喜好与优势」卡片
  if (query.includes('喜好') || query.includes('优势')) return 'personal-preferences';
  // 匹配「健康目标与痛点」卡片
  if (query.includes('目标') || query.includes('痛点')) return 'health-goals';
  // 匹配「消费能力与背景」卡片
  if (query.includes('消费能力') || query.includes('背景')) return 'consumption-ability';
  // 匹配「客户关系与服务记录」卡片
  if (query.includes('客户关系') || query.includes('服务记录')) return 'customer-relations';
  // 匹配「教育铺垫记录」卡片
  if (query.includes('教育铺垫')) return 'education-records';
  // 匹配「注意事项」卡片
  if (query.includes('注意事项') || query.includes('precautions')) return 'precautions';
  // 匹配「综合分析与咨询记录」卡片
  if (query.includes('综合分析') || query.includes('咨询记录')) return 'consultation-records';
  // 匹配「备注」卡片
  if (query.includes('备注') || query.includes('remarks')) return 'remarks';
  // 匹配「负责人与执行日期」卡片
  if (query.includes('负责人') || query.includes('执行日期')) return 'execution-date';
  
  // 兜底：提到"卡片"时默认显示资产信息卡片（演示用）
  if (query.includes('卡片')) return 'asset-info';
  
  return null;
};

