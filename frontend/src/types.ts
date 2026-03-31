// 类型定义文件：集中声明系统、任务、公告等页面数据结构。
import { LucideIcon } from 'lucide-react';

export interface System {
  id: number;
  name: string;
  icon: LucideIcon;
  count: number;
  color: string;
  bg?: string;
  text?: string;
}

export interface Work {
  id: number;
  title: string;
  system: string;
  sla: string;
  timeRange: string;
  priority: string;
  progress: number;
  description: string;
  completed: boolean;
  theme: string;
  comments: number;
  attachments: number;
  assignees: string[];
}

export interface Todo {
  id: number;
  title: string;
  system: string;
  sla: string;
  timeRange: string;
  priority: string;
  progress: number;
  description: string;
  completed: boolean;
  theme: string;
  comments: number;
  attachments: number;
  assignees: string[];
}

export interface Notice {
  id: number;
  title: string;
  date: string;
  aiSummary: string;
  read: boolean;
}

export interface Risk {
  id: number;
  title: string;
  system: string;
  sla: string;
  priority: string;
  progress: number;
  description: string;
  completed: boolean;
  theme: string;
  link?: string;
}

export interface Message {
  role: 'ai' | 'user';
  content: string;
}

export interface NavItemType {
  id: number;
  label: string;
  icon?: LucideIcon;
  active?: boolean;
  badge?: number;
  subItems?: string[];
}
