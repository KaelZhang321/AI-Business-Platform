export type PlanningMessageRole = 'ai' | 'user';

export interface PlanningMessage {
  id: string;
  role: PlanningMessageRole;
  content: string;
}

export type WorkbenchViewMode = 'PLAN' | 'HISTORY' | 'COMPARISON' | 'SUGGESTIONS' | 'FULL_INFO' | 'AI_PANEL';


export interface HistoryItem {
  id: string;
  date: string;
  type: string;
  result: string;
  detail: string;
}
