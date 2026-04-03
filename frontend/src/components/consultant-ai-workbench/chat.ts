import type { PlanningMessage, PlanningMessageRole, WorkbenchViewMode } from './types';

let planningMessageCounter = 0;

export function createPlanningMessage(role: PlanningMessageRole, content: string): PlanningMessage {
  planningMessageCounter += 1;
  return {
    id: `planning-message-${planningMessageCounter}`,
    role,
    content,
  };
}

export function getAiResponse(input: string): { response: string; viewMode?: WorkbenchViewMode; showNewPlan?: boolean } {
  if (input.includes('整理') || input.includes('信息')) {
    return {
      response: '✨ 已为您整理好客户【张三】的全量信息。包含基础画像、健康状况、已购体检方案及大会门票信息。详情已在右侧看板展示。',
      viewMode: 'FULL_INFO',
      showNewPlan: false,
    };
  }

  if (input.includes('记录') || input.includes('半年')) {
    return {
      response: '✨ 已调取【张三】近半年的治疗记录。共计 12 次治疗，包含中医调理与光电项目。',
      viewMode: 'HISTORY',
      showNewPlan: false,
    };
  }

  if (input.includes('对比') || input.includes('结果')) {
    return {
      response: '✨ 治疗结果对比分析已完成。数据显示：气虚体质改善明显，皮肤紧致度提升 15%。',
      viewMode: 'COMPARISON',
      showNewPlan: false,
    };
  }

  if (input.includes('建议') || input.includes('追踪')) {
    return {
      response: '✨ 已根据最新治疗结果生成健康追踪建议。建议加强居家饮食调理，并按期进行下月复查。',
      viewMode: 'SUGGESTIONS',
      showNewPlan: false,
    };
  }

  if (input.includes('1+x') || input.includes('规划')) {
    return {
      response: '✨ 1+X 智能规划方案已生成。已为您匹配最优消耗路径。',
      viewMode: 'PLAN',
      showNewPlan: true,
    };
  }

  return { response: '正在为您处理指令...' };
}
