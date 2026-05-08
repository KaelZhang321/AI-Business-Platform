export interface AIComponentManagementViewProps {
  setCurrentPage: (page: any) => void;
  isDarkMode: boolean;
  setIsDarkMode: (val: boolean) => void;
}

export interface CardConfig {
  id: string;
  title: string;
  type: string;
  category?: string;
  url?: string;
}

export type CardContext = 'management' | 'workbench';

export interface CardRenderProps {
  title?: string;
  hideHeader?: boolean;
  onEdit?: () => void;
  context?: CardContext;
}

export type RoleKey = 'doctor' | 'consultant' | 'sales';

export type LayoutMap = Record<RoleKey, string[]>;
