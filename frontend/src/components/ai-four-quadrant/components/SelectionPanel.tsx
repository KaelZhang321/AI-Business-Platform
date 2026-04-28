import { useRef, useState, type UIEvent } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Check, ChevronDown, Loader2, Search } from 'lucide-react'
import type { ClientOption, ReportOption } from '../types'

interface SelectionPanelProps {
  quadrantType: 'exam' | 'treatment'
  selectedClient?: ClientOption
  selectedClientId: string | null
  selectedReport?: ReportOption
  selectedReportId: string | null
  availableReports: ReportOption[]
  notes: string
  isClientDropdownOpen: boolean
  isReportDropdownOpen: boolean
  isAnalyzing: boolean
  isLoadingReports?: boolean
  clients: ClientOption[]
  isLoadingMoreClients?: boolean
  isLoadingClients?: boolean
  hasMoreClients?: boolean
  customerKeyword?: string
  onClientDropdownToggle: () => void
  onReportDropdownToggle: () => void
  onSelectClient: (id: string) => void
  onLoadMoreClients?: () => void
  onCustomerKeywordChange?: (value: string) => void
  onSelectReport: (id: string) => void
  onQuadrantTypeChange: (value: 'exam' | 'treatment') => void
  onSetNotes: (value: string) => void
  onStartAnalysis: () => void
}

export const SelectionPanel = ({
  quadrantType,
  selectedClient,
  selectedClientId,
  selectedReport,
  selectedReportId,
  availableReports,
  notes,
  isClientDropdownOpen,
  isReportDropdownOpen,
  isAnalyzing,
  isLoadingReports = false,
  clients,
  isLoadingMoreClients = false,
  isLoadingClients = false,
  hasMoreClients = false,
  customerKeyword = '',
  onClientDropdownToggle,
  onReportDropdownToggle,
  onSelectClient,
  onLoadMoreClients,
  onCustomerKeywordChange,
  onSelectReport,
  onQuadrantTypeChange,
  onSetNotes,
  onStartAnalysis,
}: SelectionPanelProps) => {
  const isTriggeringLoadRef = useRef(false)
  const [isQuadrantTypeDropdownOpen, setIsQuadrantTypeDropdownOpen] = useState(false)
  const quadrantTypeOptions: Array<{ value: 'exam' | 'treatment'; label: string; description: string }> = [
    { value: 'exam', label: '体检象限', description: '基于体检报告生成健康四象限' },
    { value: 'treatment', label: '治疗象限', description: '基于治疗场景生成治疗四象限' },
  ]
  const selectedQuadrantType = quadrantTypeOptions.find((option) => option.value === quadrantType)

  const handleClientScroll = (event: UIEvent<HTMLDivElement>) => {
    if (!onLoadMoreClients || !hasMoreClients || isLoadingMoreClients || isTriggeringLoadRef.current) {
      return
    }

    const target = event.currentTarget
    const remaining = target.scrollHeight - target.scrollTop - target.clientHeight
    if (remaining > 24) {
      return
    }

    isTriggeringLoadRef.current = true
    onLoadMoreClients()
    window.setTimeout(() => {
      isTriggeringLoadRef.current = false
    }, 200)
  }

  return (
    <>
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-2">选择输入</h2>
      </div>

      <div className="space-y-4 flex-1">
        <div className="space-y-2 relative">
          <label className="text-sm font-bold text-brand dark:text-brand-400">选择客户</label>
          <div className="w-full flex items-center px-4 py-3 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-xl text-sm focus-within:ring-2 focus-within:ring-brand/50 dark:text-white transition-all">
            <input
              value={customerKeyword}
              onChange={(event) => onCustomerKeywordChange?.(event.target.value)}
              onFocus={() => {
                if (!isClientDropdownOpen) {
                  onClientDropdownToggle()
                }
              }}
              placeholder={selectedClient ? `${selectedClient.name} (${selectedClient.phone})` : '请输入客户姓名 / 手机号'}
              className="flex-1 bg-transparent text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none"
            />
            <button type="button" onClick={onClientDropdownToggle} className="ml-2">
              <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${isClientDropdownOpen ? 'rotate-180' : ''}`} />
            </button>
          </div>

          <AnimatePresence>
            {isClientDropdownOpen && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="absolute z-50 top-full left-0 w-full mt-2 bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-xl shadow-xl overflow-hidden"
              >
                <div className="max-h-72 overflow-y-auto custom-scrollbar" onScroll={handleClientScroll}>
                  {isLoadingClients && clients.length === 0 && (
                    <div className="flex items-center justify-center py-3 text-sm text-slate-500 dark:text-slate-400">
                      <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                      客户加载中...
                    </div>
                  )}

                  {clients.length > 0 ? (
                    clients.map((client) => (
                      <button
                        key={client.id}
                        onClick={() => onSelectClient(client.id)}
                        className="w-full flex items-center px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors text-left"
                      >
                        <img src={client.avatar} alt="" className="w-8 h-8 rounded-full mr-3" />
                        <div className="flex-1">
                          <p className="text-sm font-bold text-slate-900 dark:text-white">{client.name}</p>
                          <p className="text-xs text-slate-500">{client.phone}</p>
                        </div>
                        {selectedClientId === client.id && <Check className="w-4 h-4 text-brand" />}
                      </button>
                    ))
                  ) : (
                    <div className="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">暂无客户</div>
                  )}

                  {isLoadingMoreClients && (
                    <div className="flex items-center justify-center py-2 text-xs text-slate-500 dark:text-slate-400">
                      <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                      加载更多中...
                    </div>
                  )}

                  {!hasMoreClients && clients.length > 0 && (
                    <div className="py-2 text-center text-xs text-slate-400 dark:text-slate-500">已加载全部客户</div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="space-y-2 relative">
          <label className="text-sm font-bold text-brand dark:text-brand-400">体检报告</label>
          <button
            disabled={!selectedClientId}
            onClick={onReportDropdownToggle}
            className={`w-full flex items-center justify-between px-4 py-3 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand/50 dark:text-white transition-all ${!selectedClientId ? 'opacity-50 cursor-not-allowed' : ''
              }`}
          >
            <span className={selectedReport ? 'text-slate-900 dark:text-white' : 'text-slate-400'}>
              {selectedReport ? selectedReport.title : '请先选择客户后再选择报告'}
            </span>
            <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${isReportDropdownOpen ? 'rotate-180' : ''}`} />
          </button>

          <AnimatePresence>
            {isReportDropdownOpen && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="absolute z-50 top-full left-0 w-full mt-2 bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-xl shadow-xl overflow-hidden"
              >
                {isLoadingReports ? (
                  <div className="flex items-center justify-center py-3 text-sm text-slate-500 dark:text-slate-400">
                    <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                    体检记录加载中...
                  </div>
                ) : availableReports.length > 0 ? (
                  <div className="max-h-72 overflow-y-auto custom-scrollbar">
                    {availableReports.map((report) => (
                      <button
                        key={report.id}
                        onClick={() => onSelectReport(report.id)}
                        className="w-full flex items-center px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors text-left"
                      >
                        <div className="flex-1">
                          <p className="text-sm font-bold text-slate-900 dark:text-white">{report.title}</p>
                          <p className="text-xs text-slate-500">{report.date}</p>
                        </div>
                        {selectedReportId === report.id && <Check className="w-4 h-4 text-brand" />}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">暂无体检记录</div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="space-y-2 relative">
          <label className="text-sm font-bold text-brand dark:text-brand-400">象限类型</label>
          <button
            type="button"
            onClick={() => setIsQuadrantTypeDropdownOpen((open) => !open)}
            className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand/50 dark:text-white transition-all"
          >
            <span className="text-left">
              <span className="block text-sm font-bold text-slate-900 dark:text-white">
                {selectedQuadrantType?.label ?? '请选择象限类型'}
              </span>
              <span className="mt-0.5 block text-xs text-slate-500 dark:text-slate-400">
                {selectedQuadrantType?.description ?? '选择本次分析的象限类型'}
              </span>
            </span>
            <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${isQuadrantTypeDropdownOpen ? 'rotate-180' : ''}`} />
          </button>

          <AnimatePresence>
            {isQuadrantTypeDropdownOpen && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="absolute z-50 top-full left-0 w-full mt-2 bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-xl shadow-xl overflow-hidden"
              >
                {quadrantTypeOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => {
                      onQuadrantTypeChange(option.value)
                      setIsQuadrantTypeDropdownOpen(false)
                    }}
                    className="w-full flex items-center px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors text-left"
                  >
                    <div className="flex-1">
                      <p className="text-sm font-bold text-slate-900 dark:text-white">{option.label}</p>
                      <p className="text-xs text-slate-500">{option.description}</p>
                    </div>
                    {quadrantType === option.value && <Check className="w-4 h-4 text-brand" />}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-bold text-brand dark:text-brand-400">补充备注给AI小助手</label>
          <textarea
            placeholder="记录当前症状、近期变化或问诊补充，AI将结合备注和报告综合判断四象限"
            className="w-full p-4 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand/50 min-h-[100px] resize-none dark:text-white"
            value={notes}
            onChange={(e) => onSetNotes(e.target.value)}
          />
        </div>

        <button
          onClick={onStartAnalysis}
          className={`w-full py-3 font-bold rounded-xl transition-all flex items-center justify-center space-x-2 ${selectedClientId && selectedReportId && !isAnalyzing
            ? 'bg-brand text-white hover:bg-brand-hover shadow-lg shadow-brand/20'
            : 'bg-slate-100 dark:bg-slate-700 text-slate-400 dark:text-slate-500 cursor-not-allowed'
            }`}
          disabled={!selectedClientId || !selectedReportId || isAnalyzing}
        >
          {isAnalyzing ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>AI 深度分析中...</span>
            </>
          ) : (
            <>
              <Search className="w-4 h-4" />
              <span>开始联合分析</span>
            </>
          )}
        </button>
      </div>

      <div className="mt-4 space-y-3 shrink-0">
        <h4 className="text-sm font-bold text-slate-900 dark:text-white mb-4">页面提示</h4>
        <div className="flex items-start space-x-2 text-sm text-slate-600 dark:text-slate-400">
          <div className="w-1.5 h-1.5 rounded-full bg-brand mt-1.5 shrink-0" />
          <p>客户选定后自动解锁体检报告选择。</p>
        </div>
        <div className="flex items-start space-x-2 text-sm text-slate-600 dark:text-slate-400">
          <div className="w-1.5 h-1.5 rounded-full bg-brand mt-1.5 shrink-0" />
          <p>未完成基础输入时，右侧只展示四象限骨架。</p>
        </div>
        <div className="flex items-start space-x-2 text-sm text-slate-600 dark:text-slate-400">
          <div className="w-1.5 h-1.5 rounded-full bg-brand mt-1.5 shrink-0" />
          <p>报告选中后可补充备注，AI 会结合两类信息自动开始分析。</p>
        </div>
      </div>
    </>
  )
}
