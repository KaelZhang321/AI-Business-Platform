// 类型定义文件：集中声明系统、任务、公告等页面数据结构。
import { LucideIcon } from 'lucide-react';

/** 系统模块 —— 首页"快捷入口"网格中每个系统的描述 */
export interface System {
  /** 系统唯一标识 */
  id: number;
  /** 系统名称（如"到院接待""预约管理"） */
  name: string;
  /** 系统图标组件 (Lucide) */
  icon: LucideIcon;
  /** 未处理/待办数量 */
  count: number;
  /** 图标文字色 Tailwind 类名 */
  color: string;
  /** 背景色 Tailwind 类名（可选） */
  bg?: string;
  /** 文字色 Tailwind 类名（可选） */
  text?: string;
}

/** 工作项 —— 工作台"我的工作"列表中的单条任务 */
export interface Work {
  /** 工作项唯一标识 */
  id: number;
  /** 工作项标题 */
  title: string;
  /** 所属子系统名称 */
  system: string;
  /** SLA 时限描述（如"今日 17:00 前"） */
  sla: string;
  /** 时间范围描述（如"08:30 am - 11:20 am"） */
  timeRange: string;
  /** 优先级：high / medium / low */
  priority: string;
  /** 完成进度百分比 0-100 */
  progress: number;
  /** 工作项描述 */
  description: string;
  /** 是否已完成 */
  completed: boolean;
  /** 主题色标识（用于卡片色条） */
  theme: string;
  /** 评论数量 */
  comments: number;
  /** 附件数量 */
  attachments: number;
  /** 参与人头像 URL 列表 */
  assignees: string[];
}

/** 待办项 —— 工作台"待办事项"列表中的单条记录 */
export interface Todo {
  /** 待办项唯一标识 */
  id: number;
  /** 待办项标题 */
  title: string;
  /** 所属子系统名称 */
  system: string;
  /** SLA 时限描述 */
  sla: string;
  /** 时间范围描述 */
  timeRange: string;
  /** 优先级：high / medium / low */
  priority: string;
  /** 完成进度百分比 0-100 */
  progress: number;
  /** 待办项描述 */
  description: string;
  /** 是否已完成 */
  completed: boolean;
  /** 主题色标识 */
  theme: string;
  /** 评论数量 */
  comments: number;
  /** 附件数量 */
  attachments: number;
  /** 参与人头像 URL 列表 */
  assignees: string[];
}

/** 通知公告 —— 顶部滚动条和公告列表使用 */
export interface Notice {
  /** 公告唯一标识 */
  id: number;
  /** 公告标题 */
  title: string;
  /** 发布日期（YYYY-MM-DD） */
  date: string;
  /** AI 摘要（对原文内容的智能概括） */
  aiSummary: string;
  /** 当前用户是否已读 */
  read: boolean;
}

/** 风险项 —— 工作台"风险告警"列表中的单条记录 */
export interface Risk {
  /** 风险项唯一标识 */
  id: number;
  /** 风险标题 */
  title: string;
  /** 来源系统名称 */
  system: string;
  /** SLA 要求描述 */
  sla: string;
  /** 优先级：high / medium / low */
  priority: string;
  /** 处理进度百分比 0-100 */
  progress: number;
  /** 风险描述 */
  description: string;
  /** 是否已处理完成 */
  completed: boolean;
  /** 主题色标识 */
  theme: string;
  /** 可选的关联链接文案 */
  link?: string;
}

/** 聊天消息 —— AI 助手对话气泡数据 */
export interface Message {
  /** 角色：ai 表示 AI 回复，user 表示用户输入 */
  role: 'ai' | 'user';
  /** 消息文本内容 */
  content: string;
}

/** 导航菜单项 —— 侧边栏一级/二级导航条目 */
export interface NavItemType {
  /** 导航项唯一标识 */
  id: number;
  /** 显示文本 */
  label: string;
  /** 图标组件（可选） */
  icon?: LucideIcon;
  /** 是否处于激活态 */
  active?: boolean;
  /** 角标数字（未读数等，可选） */
  badge?: number;
  /** 子菜单标签列表（可选） */
  subItems?: string[];
}
