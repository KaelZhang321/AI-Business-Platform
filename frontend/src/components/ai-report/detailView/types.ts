import type { LucideIcon } from 'lucide-react';

export interface CustomerRecord {
  id: string | number;
  name: string;
  gender: string;
  age: number;
  lastCheckDate: string;
  aiJudgment: string;
  keyAbnormal: string;
  customerId?: string;
  encryptedIdCard?: string | null;
  idCardObfuscated?: string | null;
  encryptedPhone?: string | null;
  phoneObfuscated?: string | null;
  typeName?: string | null;
  storeName?: string | null;
  mainTeacherName?: string | null;
  subTeacherName?: string | null;
  latestExamDate?: string | null;
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
