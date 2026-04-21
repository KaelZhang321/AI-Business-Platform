export type AIFourQuadrantPage =
  | 'dashboard'
  | 'health-butler'
  | 'function-square'
  | 'ai-diagnosis'
  | 'ai-report-comparison-detail'
  | 'ai-four-quadrant'

export interface AIFourQuadrantViewProps {
  setCurrentPage: (page: AIFourQuadrantPage) => void
  isDarkMode: boolean
  setIsDarkMode: (value: boolean) => void
  hideHeader?: boolean
  navigationParams?: {
    customerId?: string | number
    [key: string]: unknown
  }
}

export interface ClientOption {
  id: string
  name: string
  gender?: string
  age?: number
  phone: string
  avatar: string
  encryptedIdCard?: string | null
}

export interface ReportOption {
  id: string
  title: string
  date: string
  studyId?: string
}

export interface QuadrantItem {
  id: string
  content: string
  category?: string
}

export type QuadrantKey = 'monitoring' | 'intervention' | 'maintenance' | 'prevention'

export type QuadrantData = Record<QuadrantKey, QuadrantItem[]>

export interface AnalysisResultSnapshot {
  monitoring: QuadrantItem[]
  intervention: QuadrantItem[]
  maintenance: QuadrantItem[]
  prevention: QuadrantItem[]
  conclusion: string
  clientInfo: string
  reportInfo: string
  riskLevel: string
  score: number
}

export interface ChatMessage {
  id: number
  sender: 'ai' | 'user'
  text: string
}
