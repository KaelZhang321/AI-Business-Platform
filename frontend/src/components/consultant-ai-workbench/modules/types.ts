import type { AppPage } from '../../../navigation';

export type SavedLayout = {
  id: string;
  name: string;
  cards: string[];
  customerId?: string;
};

export type ChatHistoryItem = {
  role: 'user' | 'assistant';
  content: string;
};

export type AIResultItem = {
  id: number;
  type: string;
  title: string;
  content: string;
};

export type CustomerRecord = {
  id: string;
  name: string;
  age?: number;
  gender?: string;
  phone?: string;
  idCard?: string;
  lastCheckDate?: string;
  aiJudgment?: string;
  keyAbnormal?: string;
  [key: string]: unknown;
};

export interface ConsultantAIWorkbenchProps {
  setCurrentPage?: (page: AppPage) => void;
  setNavigationParams?: (params: Record<string, unknown>) => void;
}
