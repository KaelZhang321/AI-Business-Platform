import type { LucideIcon } from 'lucide-react';

export interface CustomerRecord {
  id: number;
  name: string;
  gender: string;
  age: number;
  lastCheckDate: string;
  aiJudgment: string;
  keyAbnormal: string;
}

export interface StatCard {
  label: string;
  value: string;
  color: string;
  dot: string;
  desc: string;
  icon: LucideIcon;
  bg: string;
}

export type DetailViewMode = 'card' | 'list';
