import type { LucideIcon } from 'lucide-react';

/** 客户记录（报告详情页的客户数据行） */
export interface CustomerRecord {
  /** 客户 ID */
  id: string | number;
  /** 客户姓名 */
  name: string;
  /** 性别 */
  gender: string;
  /** 年龄 */
  age: number;
  /** 最近体检日期 */
  lastCheckDate: string;
  /** AI 判断结论 */
  aiJudgment: string;
  /** 关键异常指标摘要 */
  keyAbnormal: string;
  /** 客户业务 ID（可选） */
  customerId?: string;
  /** 加密身份证号（可选） */
  encryptedIdCard?: string | null;
  /** 脱敏身份证号（可选） */
  idCardObfuscated?: string | null;
  /** 加密手机号（可选） */
  encryptedPhone?: string | null;
  /** 脱敏手机号（可选） */
  phoneObfuscated?: string | null;
  /** 客户类型名称（可选） */
  typeName?: string | null;
  /** 所属门店名称（可选） */
  storeName?: string | null;
  /** 主管老师姓名（可选） */
  mainTeacherName?: string | null;
  /** 副管老师姓名（可选） */
  subTeacherName?: string | null;
  /** 最新一次体检日期（可选） */
  latestExamDate?: string | null;
}

/** 统计卡片数据结构 */
export interface StatCard {
  /** 指标标签 */
  label: string;
  /** 指标数值（已格式化） */
  value: string;
  /** 主题色 */
  color: string;
  /** 圆点颜色 */
  dot: string;
  /** 指标描述 */
  desc: string;
  /** 图标组件 */
  icon: LucideIcon;
  /** 背景色 */
  bg: string;
}

/** 详情视图切换模式：卡片视图 / 列表视图 */
export type DetailViewMode = 'card' | 'list';

