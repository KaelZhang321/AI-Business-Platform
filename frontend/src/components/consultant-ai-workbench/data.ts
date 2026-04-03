import { Activity, Moon, Utensils, type LucideIcon } from 'lucide-react';
import type { HistoryItem } from './types';

export interface SuggestionItem {
  id: string;
  title: string;
  content: string;
  icon: LucideIcon;
}

export const historyItems: HistoryItem[] = [
  { id: 'history-1', date: '2026-03-10', type: '中医调理', result: '良好', detail: '气虚症状有所缓解' },
  { id: 'history-2', date: '2026-02-15', type: '光电抗衰', result: '显著', detail: '面部紧致度提升' },
  { id: 'history-3', date: '2026-01-20', type: '中医调理', result: '一般', detail: '睡眠质量待改善' },
  { id: 'history-4', date: '2025-12-05', type: '年度体检', result: '完成', detail: '各项指标基本稳定' },
];

export const suggestionItems: SuggestionItem[] = [
  { id: 'diet', title: '饮食建议', content: '增加山药、大枣等补气食物，避免生冷。', icon: Utensils },
  { id: 'exercise', title: '运动建议', content: '每日进行 30 分钟八段锦或太极拳，不宜剧烈运动。', icon: Activity },
  { id: 'sleep', title: '作息建议', content: '晚间 10:30 前入睡，保证 7-8 小时高质量睡眠。', icon: Moon },
];

export const quickPromptActions = [
  '整理张三的所有信息',
  '查看张三近半年治疗记录',
  '对比张三治疗结果',
  '生成健康追踪建议',
] as const;
