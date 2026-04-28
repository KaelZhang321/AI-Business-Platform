import { motion } from 'motion/react'
import { FileText, Loader2 } from 'lucide-react'
import type { ClientOption, ReportOption } from '../types'

interface StatusBannerProps {
  quadrantType: 'exam' | 'treatment'
  showResults: boolean
  isAnalyzing: boolean
  selectedClientId: string | null
  selectedReportId: string | null
  selectedClient?: ClientOption
  selectedReport?: ReportOption
  notes: string
  analysisProgress: number
  analysisStep: string
}

export const StatusBanner = ({
  quadrantType,
  showResults,
  isAnalyzing,
  selectedClientId,
  selectedReportId,
  selectedClient,
  selectedReport,
  notes,
  analysisProgress,
  analysisStep,
}: StatusBannerProps) => {
  const quadrantTypeLabel = quadrantType === 'treatment' ? '治疗' : '体检'

  if (showResults) {
    return (
      <div className="bg-[#1E293B] dark:bg-slate-800 rounded-2xl p-6 flex items-center justify-between shadow-sm shrink-0">
        <div className="space-y-3">
          <h2 className="text-2xl font-bold text-white">AI 已生成可编辑{quadrantTypeLabel}四象限结果</h2>
          <p className="text-sm text-slate-300">医生可以基于 AI 的初始归类直接做二次判断。添加、删除和拖拽能力都内聚在四象限结果区中。</p>
          <div className="flex items-center space-x-3 pt-2">
            <span className="px-4 py-1.5 bg-slate-700/50 text-slate-300 text-xs rounded-full border border-slate-600">立即干预 4项</span>
            <span className="px-4 py-1.5 bg-slate-700/50 text-slate-300 text-xs rounded-full border border-slate-600">支持拖拽调整</span>
            <span className="px-4 py-1.5 bg-slate-700/50 text-slate-300 text-xs rounded-full border border-slate-600">支持手动添加/删除</span>
          </div>
        </div>
        <div className="bg-slate-800/80 border border-slate-600 rounded-xl p-4 w-64 shrink-0">
          <p className="text-xs text-slate-400 mb-2">当前重点</p>
          <p className="text-sm font-bold text-white">结果已生成，可继续人工修正</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-[#1E293B] dark:bg-slate-800 rounded-2xl p-6 flex items-center justify-between shadow-sm transition-colors duration-300 shrink-0 relative overflow-hidden">
      {isAnalyzing && (
        <motion.div
          initial={{ x: '-100%' }}
          animate={{ x: '100%' }}
          transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
          className="absolute inset-0 bg-gradient-to-r from-transparent via-brand/10 to-transparent pointer-events-none"
        />
      )}

      <div className="space-y-2 relative z-10">
        <div className="flex items-center space-x-3">
          <h2 className="text-xl font-bold text-white">
            {isAnalyzing
              ? 'AI 正在进行多维联合评估...'
              : selectedClientId && selectedReportId
                ? '信息已完善，可开始 AI 联合评估'
                : '请先完成客户与体检报告选择'}
          </h2>
        </div>
        <p className="text-sm text-slate-400">
          {isAnalyzing
            ? `正在处理：${analysisStep}`
            : selectedClientId && selectedReportId
              ? '“开始联合分析”按钮，AI 将结合体检报告与您的备注，自动生成四象限健康评估。'
              : '页面初始化为未选择状态，右侧仅保留四象限工作区结构；可先录入备注，再由 AI 联合评估。'}
        </p>

        {isAnalyzing && (
          <div className="w-full max-w-md mt-4">
            <div className="flex justify-between text-xs text-brand-300 mb-1">
              <span>分析进度</span>
              <span>{Math.round(analysisProgress)}%</span>
            </div>
            <div className="h-1.5 w-full bg-slate-700 rounded-full overflow-hidden">
              <motion.div className="h-full bg-brand" initial={{ width: 0 }} animate={{ width: `${analysisProgress}%` }} />
            </div>
          </div>
        )}

        <div className="flex items-center space-x-2 pt-2">
          {selectedClient && (
            <div className="flex items-center px-3 py-1 bg-brand/20 text-brand-300 border border-brand/30 text-xs rounded-full text-slate-300">
              <img src={selectedClient.avatar} alt="" className="w-4 h-4 rounded-full mr-2" />
              <span>{selectedClient.name}</span>
            </div>
          )}
          {selectedReport && (
            <div className="flex items-center px-3 py-1 bg-brand/20 text-brand-300 border border-brand/30 text-xs rounded-full text-slate-300">
              <FileText className="w-3 h-3 mr-2" />
              <span>{selectedReport.title}</span>
            </div>
          )}
          <span
            className={`px-3 py-1 text-xs rounded-full border ${notes ? 'bg-brand/20 text-brand-300 border-brand/30' : 'bg-slate-700/50 text-slate-300 border-slate-600'
              }`}
          >
            {notes ? '已填备注' : '无备注'}
          </span>
        </div>
      </div>

      <div className="bg-slate-800/50 dark:bg-slate-900/50 border border-slate-700 rounded-xl p-4 w-64 shrink-0 relative z-10">
        <p className="text-xs text-slate-400 mb-1">当前状态</p>
        <div className="flex items-center space-x-2">
          {isAnalyzing ? <Loader2 className="w-4 h-4 text-brand animate-spin" /> : <div className="w-2 h-2 rounded-full bg-amber-500" />}
          <p className="text-sm font-bold text-white">{isAnalyzing ? 'AI 深度分析中' : '等待激活'}</p>
        </div>
        {isAnalyzing && <p className="text-[10px] text-slate-500 mt-1 truncate">{analysisStep}</p>}
      </div>
    </div>
  )
}
