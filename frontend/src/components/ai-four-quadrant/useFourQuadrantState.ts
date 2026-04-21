import { useEffect, useState } from 'react'
import { getCardIdFromQuery } from '../../utils/cardMatcher'
import { aiReportApi } from '../../services/api/aiReportApi'
import { aIFourQuadrantViewApi } from '../../services/api/aIFourQuadrantViewApi'
import {
  ANALYSIS_STEPS,
  EMPTY_QUADRANT_DATA,
  INITIAL_ANALYSIS_RESULTS,
  INITIAL_CHAT_MESSAGES,
} from './constants'
import type { AIFourQuadrantViewProps, ClientOption, QuadrantData, ReportOption } from './types'

type RawCustomerItem = {
  customerId?: string | number | null
  patientName?: string | null
  gender?: string | null
  age?: number | string | null
  phoneObfuscated?: string | null
  encryptedIdCard?: string | null
}

type CustomerListApiResponse = {
  data?: RawCustomerItem[] | { data?: RawCustomerItem[] }
}

type RawExamSessionItem = {
  id?: string | number | null
  sessionId?: string | number | null
  studyId?: string | number | null
  study_id?: string | number | null
  examDate?: string | null
  checkDate?: string | null
  createdAt?: string | null
  reportName?: string | null
  title?: string | null
  packageName?: string | null
  examTime?: string | null
}

type ExamSessionListApiResponse = {
  data?: RawExamSessionItem[] | { data?: RawExamSessionItem[] }
}

const FALLBACK_AVATAR = 'https://i.pravatar.cc/150?u=customer'

const toClientOption = (item: RawCustomerItem, index: number): ClientOption => {
  const id = item.customerId != null ? String(item.customerId) : `customer-${Date.now()}-${index}`
  return {
    id,
    name: item.patientName?.trim() || '未知客户',
    gender: item.gender || undefined,
    age: Number(item.age ?? 0),
    phone: item.phoneObfuscated?.trim() || '暂无手机号',
    avatar: `https://i.pravatar.cc/150?u=${id}` || FALLBACK_AVATAR,
    encryptedIdCard: item.encryptedIdCard ?? null,
  }
}

const parseCustomerList = (payload: unknown): RawCustomerItem[] => {
  if (Array.isArray(payload)) {
    return payload as RawCustomerItem[]
  }

  const response = payload as CustomerListApiResponse | undefined
  if (Array.isArray(response?.data)) {
    return response?.data as RawCustomerItem[]
  }

  if (response?.data && typeof response.data === 'object') {
    const nested = response.data as { data?: RawCustomerItem[] }
    if (Array.isArray(nested.data)) {
      return nested.data
    }
  }

  return []
}

const parseExamSessionList = (payload: unknown): RawExamSessionItem[] => {
  if (Array.isArray(payload)) {
    return payload as RawExamSessionItem[]
  }

  const response = payload as ExamSessionListApiResponse | undefined
  if (Array.isArray(response?.data)) {
    return response.data as RawExamSessionItem[]
  }

  if (response?.data && typeof response.data === 'object') {
    const nested = response.data as { data?: RawExamSessionItem[] }
    if (Array.isArray(nested.data)) {
      return nested.data
    }
  }

  return []
}

const toReportOption = (item: RawExamSessionItem, index: number): ReportOption => {
  const idValue = item.sessionId ?? item.id
  const id = idValue != null ? String(idValue) : `report-${Date.now()}-${index}`
  const title = item.packageName?.trim() || item.title?.trim() || `体检记录 ${index + 1}`
  const date = item.examTime || item.checkDate || item.createdAt || '暂无日期'
  const studyIdValue = item.studyId ?? item.study_id ?? item.sessionId ?? item.id
  const studyId = studyIdValue != null ? String(studyIdValue) : id
  return { id, title, date, studyId }
}

const normalizeSex = (gender?: string) => {
  if (!gender) return '男'
  if (gender.includes('女')) return '女'
  return '男'
}

const toQuadrantItems = (items: string[] = [], category?: 'abnormal' | 'recommendation') =>
  items
    .filter((value) => typeof value === 'string' && value.trim())
    .map((value, index) => ({
      id: `${category ?? 'item'}-${Date.now()}-${index}-${Math.random().toString(36).slice(2, 8)}`,
      content: value.trim(),
      category,
    }))

const parseQuadrantResult = (response: unknown) => {
  const data = response as { quadrants?: Array<{ q_code?: string; abnormal_indicators?: string[]; recommendation_plans?: string[] }> } | undefined
  const quadrants = data?.quadrants ?? []

  const getByCode = (code: string) => quadrants.find((item) => item.q_code === code)

  const q1 = getByCode('q1')
  const q2 = getByCode('q2')
  const q3 = getByCode('q3')
  const q4 = getByCode('q4')

  return {
    prevention: [...toQuadrantItems(q1?.abnormal_indicators, 'abnormal'), ...toQuadrantItems(q1?.recommendation_plans, 'recommendation')],
    monitoring: [...toQuadrantItems(q2?.abnormal_indicators, 'abnormal'), ...toQuadrantItems(q2?.recommendation_plans, 'recommendation')],
    maintenance: [...toQuadrantItems(q3?.abnormal_indicators, 'abnormal'), ...toQuadrantItems(q3?.recommendation_plans, 'recommendation')],
    intervention: [...toQuadrantItems(q4?.abnormal_indicators, 'abnormal'), ...toQuadrantItems(q4?.recommendation_plans, 'recommendation')],
  }
}

export const useFourQuadrantState = (navigationParams: AIFourQuadrantViewProps['navigationParams']) => {
  const CLIENT_PAGE_SIZE = 20
  const DEFAULT_CUSTOMER_KEYWORD = ''
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null)
  const [notes, setNotes] = useState('')
  const [customerKeyword, setCustomerKeyword] = useState(DEFAULT_CUSTOMER_KEYWORD)

  const [isClientDropdownOpen, setIsClientDropdownOpen] = useState(false)
  const [isReportDropdownOpen, setIsReportDropdownOpen] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [showResults, setShowResults] = useState(false)
  const [isEnlarged, setIsEnlarged] = useState(false)

  const [chatMessages, setChatMessages] = useState(INITIAL_CHAT_MESSAGES)
  const [chatInput, setChatInput] = useState('')

  const [quadrantData, setQuadrantData] = useState<QuadrantData>(EMPTY_QUADRANT_DATA)

  const [clients, setClients] = useState<ClientOption[]>([])
  const [isLoadingClients, setIsLoadingClients] = useState(false)
  const [isLoadingMoreClients, setIsLoadingMoreClients] = useState(false)
  const [clientPage, setClientPage] = useState(1)
  const [hasMoreClients, setHasMoreClients] = useState(true)

  const [availableReports, setAvailableReports] = useState<ReportOption[]>([])
  const [isLoadingReports, setIsLoadingReports] = useState(false)

  const selectedClient = clients.find((c) => c.id === selectedClientId)
  const selectedReport = availableReports.find((r) => r.id === selectedReportId)

  const [analysisProgress, setAnalysisProgress] = useState(0)
  const [analysisStep, setAnalysisStep] = useState('')

  const fetchClients = async (pageNo: number, append = false, keyword = customerKeyword) => {
    if (append) {
      if (isLoadingClients || isLoadingMoreClients || !hasMoreClients) {
        return
      }
      setIsLoadingMoreClients(true)
    } else {
      setIsLoadingClients(true)
      setHasMoreClients(true)
    }

    try {
      const response = await aiReportApi.getcustomersListApi({
        queryParams: {},
        body: {
          customerInfo: keyword.trim(),
        },
        page: String(pageNo),
        size: String(CLIENT_PAGE_SIZE),
      })

      const list = parseCustomerList(response)
      const mapped = list.map(toClientOption)

      setClients((prev) => {
        if (!append) {
          return mapped
        }
        return Array.from(new Map([...prev, ...mapped].map((item) => [item.id, item])).values())
      })
      setClientPage(pageNo)
      setHasMoreClients(mapped.length >= CLIENT_PAGE_SIZE)

      if (!append) {
        if (mapped.length === 0) {
          setSelectedClientId(null)
          return
        }

        if (navigationParams?.customerId) {
          const idFromNav = String(navigationParams.customerId)
          const exists = mapped.some((item) => item.id === idFromNav)
          const selectedId = exists ? idFromNav : mapped[0].id
          setSelectedClientId(selectedId)
          const selectedItem = mapped.find((item) => item.id === selectedId)
          setCustomerKeyword(selectedItem?.name ?? '')
          return
        }

        setSelectedClientId((prev) => {
          if (prev && mapped.some((item) => item.id === prev)) {
            return prev
          }
          // const firstId = mapped[0].id
          // const firstItem = mapped.find((item) => item.id === firstId)
          // setCustomerKeyword(firstItem?.name ?? '')
          return ''
        })
      }
    } catch (error) {
      console.error('getcustomersListApi error:', error)
      if (!append) {
        setClients([])
        setSelectedClientId(null)
        setHasMoreClients(false)
      }
    } finally {
      if (append) {
        setIsLoadingMoreClients(false)
      } else {
        setIsLoadingClients(false)
      }
    }
  }

  useEffect(() => {
    let mounted = true

    const loadFirstPage = async () => {
      if (!mounted) return
      await fetchClients(1, false, customerKeyword)
    }

    loadFirstPage()

    return () => {
      mounted = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigationParams])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetchClients(1, false, customerKeyword)
    }, 300)

    return () => {
      window.clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerKeyword])

  const loadMoreClients = async () => {
    if (isLoadingClients || isLoadingMoreClients || !hasMoreClients) {
      return
    }
    await fetchClients(clientPage + 1, true, customerKeyword)
  }

  useEffect(() => {
    if (!selectedClientId) {
      setSelectedReportId(null)
      setAvailableReports([])
      setQuadrantData(EMPTY_QUADRANT_DATA)
      setShowResults(false)
      return
    }

    setSelectedReportId(null)
    setAvailableReports([])
    setQuadrantData(EMPTY_QUADRANT_DATA)
    setShowResults(false)
  }, [selectedClientId])

  useEffect(() => {
    if (!selectedClientId) {
      return
    }

    const targetClient = clients.find((item) => item.id === selectedClientId)
    const encryptedIdCard = targetClient?.encryptedIdCard?.trim()
    if (!encryptedIdCard) {
      setAvailableReports([])
      return
    }

    let mounted = true
    setIsLoadingReports(true)

    aiReportApi
      .getPatientExamSessionsApi({ idCard: encryptedIdCard })
      .then((response) => {
        if (!mounted) return
        const sessions = parseExamSessionList(response)
        const reports = sessions.map(toReportOption)
        setAvailableReports(reports)
        if (reports.length > 0) {
          setSelectedReportId((prev) => {
            if (prev && reports.some((report) => report.id === prev)) {
              return prev
            }
            return reports[0].id
          })
        }
      })
      .catch((error) => {
        console.error('getPatientExamSessionsApi error:', error)
        if (!mounted) return
        setAvailableReports([])
      })
      .finally(() => {
        if (mounted) {
          setIsLoadingReports(false)
        }
      })

    return () => {
      mounted = false
    }
  }, [selectedClientId, clients])

  const handleStartAnalysis = async () => {
    if (!selectedClientId || !selectedReportId) return

    setIsAnalyzing(true)
    setAnalysisProgress(0)
    setQuadrantData(EMPTY_QUADRANT_DATA)

    let stepIdx = 0
    setAnalysisStep(ANALYSIS_STEPS[0])

    const interval = setInterval(() => {
      setAnalysisProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval)
          return 100
        }
        const next = prev + (Math.random() * 10 + 2)
        const currentStepIdx = Math.min(Math.floor((next / 100) * ANALYSIS_STEPS.length), ANALYSIS_STEPS.length - 1)
        if (currentStepIdx !== stepIdx) {
          stepIdx = currentStepIdx
          setAnalysisStep(ANALYSIS_STEPS[stepIdx])
        }
        return next > 100 ? 100 : next
      })
    }, 150)

    try {
      const sex = normalizeSex(selectedClient?.gender)
      const age = Number(selectedClient?.age ?? 0)
      const studyId = selectedReport?.studyId?.trim() || String(selectedReportId)
      const payload = {
        sex,
        age: Number.isFinite(age) ? age : 0,
        study_id: '2604150032' || studyId,
        single_exam_items: [] as string[],
        chief_complaint_text: notes.trim(),
        quadrant_type: 'exam'
      }

      const response = await aIFourQuadrantViewApi.getHealthQuadrantAnalysisApi(payload)
      const mapped = parseQuadrantResult(response)

      clearInterval(interval)
      setQuadrantData({
        monitoring: mapped.monitoring.length > 0 ? mapped.monitoring : [...INITIAL_ANALYSIS_RESULTS.monitoring],
        intervention: mapped.intervention.length > 0 ? mapped.intervention : [...INITIAL_ANALYSIS_RESULTS.intervention],
        maintenance: mapped.maintenance.length > 0 ? mapped.maintenance : [...INITIAL_ANALYSIS_RESULTS.maintenance],
        prevention: mapped.prevention.length > 0 ? mapped.prevention : [...INITIAL_ANALYSIS_RESULTS.prevention],
      })
      setAnalysisProgress(100)
      setShowResults(true)
    } catch (error) {
      console.error('getHealthQuadrantAnalysisApi error:', error)
      clearInterval(interval)
      setQuadrantData({
        monitoring: [...INITIAL_ANALYSIS_RESULTS.monitoring],
        intervention: [...INITIAL_ANALYSIS_RESULTS.intervention],
        maintenance: [...INITIAL_ANALYSIS_RESULTS.maintenance],
        prevention: [...INITIAL_ANALYSIS_RESULTS.prevention],
      })
      setAnalysisProgress(100)
      setShowResults(true)
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleSendMessage = () => {
    if (!chatInput.trim()) return

    const currentInput = chatInput.trim()
    const newUserMsg = { id: Date.now(), sender: 'user' as const, text: currentInput }
    setChatMessages((prev) => [...prev, newUserMsg])
    setChatInput('')

    setIsAnalyzing(true)
    setAnalysisProgress(0)
    setAnalysisStep('正在结合补充信息重新评估...')

    const interval = setInterval(() => {
      setAnalysisProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval)
          return 100
        }
        return prev + (Math.random() * 20 + 10)
      })
    }, 200)

    setTimeout(() => {
      clearInterval(interval)
      setIsAnalyzing(false)
      setAnalysisProgress(100)

      const cardId = getCardIdFromQuery(currentInput)
      if (cardId) {
        const aiResponse = { id: Date.now() + 1, sender: 'ai' as const, text: `好的，为您调取相关卡片：\n[CARD:${cardId}]` }
        setChatMessages((prev) => [...prev, aiResponse])
        return
      }

      if (currentInput === '补充窦性心率异常') {
        const aiResponse = { id: Date.now() + 1, sender: 'ai' as const, text: '已为您将“窦性心率异常”添加到定期检测区。' }
        setChatMessages((prev) => [...prev, aiResponse])

        setQuadrantData((prev) => ({
          ...prev,
          monitoring: [...prev.monitoring, { id: `m-${Date.now()}`, content: '窦性心率异常' }],
        }))
        return
      }

      const aiResponse = { id: Date.now() + 1, sender: 'ai' as const, text: '已收到您的补充信息，并根据最新情况更新了四象限结果。' }
      setChatMessages((prev) => [...prev, aiResponse])

      setQuadrantData((prev) => ({
        ...prev,
        intervention: [...prev.intervention, { id: `i-${Date.now()}`, content: currentInput }],
      }))
    }, 2500)
  }

  return {
    selectedClientId,
    setSelectedClientId,
    selectedReportId,
    setSelectedReportId,
    notes,
    setNotes,
    customerKeyword,
    setCustomerKeyword,
    isClientDropdownOpen,
    setIsClientDropdownOpen,
    isReportDropdownOpen,
    setIsReportDropdownOpen,
    isAnalyzing,
    isLoadingReports,
    showResults,
    isEnlarged,
    setIsEnlarged,
    chatMessages,
    chatInput,
    setChatInput,
    quadrantData,
    setQuadrantData,
    clients,
    isLoadingClients,
    isLoadingMoreClients,
    hasMoreClients,
    loadMoreClients,
    selectedClient,
    availableReports,
    selectedReport,
    analysisProgress,
    analysisStep,
    handleStartAnalysis,
    handleSendMessage,
  }
}
