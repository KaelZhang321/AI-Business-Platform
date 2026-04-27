import { ChevronLeft, Moon, Sun } from 'lucide-react'
import type { AIFourQuadrantPage, ClientOption } from '../types'

interface FourQuadrantHeaderProps {
  hideHeader?: boolean
  selectedClient?: ClientOption
  isDarkMode: boolean
  setIsDarkMode: (value: boolean) => void
  setCurrentPage: (page: AIFourQuadrantPage) => void
}

export const FourQuadrantHeader = ({
  hideHeader = false,
  selectedClient,
  isDarkMode,
  setIsDarkMode,
  setCurrentPage,
}: FourQuadrantHeaderProps) => {
  if (hideHeader) return null

  return (
    <div className="flex items-center justify-between px-8 pt-4 shrink-0">
      <div className="flex items-center space-x-4">
        <button
          onClick={() => setCurrentPage('function-square')}
          className="p-2 bg-white dark:bg-slate-800 rounded-xl shadow-sm hover:shadow-md transition-all text-slate-500 dark:text-slate-400 hover:text-brand dark:hover:text-brand-400"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">AI四象限健康评估</h1>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            医生进入页面后默认看到空白四象限，先选择客户与体检报告，也可补充当前问诊备注。
          </p>
        </div>
      </div>
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2">
          {/* <span className="px-3 py-1 bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400 text-xs rounded-full border border-blue-100 dark:border-blue-800">
            医生身份
          </span> */}
          <span
            className={`px-3 py-1 text-xs rounded-full border ${selectedClient
              ? 'bg-green-50 text-green-600 dark:bg-green-900/30 dark:text-green-400 border-green-100 dark:border-green-800'
              : 'bg-red-50 text-red-500 dark:bg-red-900/30 dark:text-red-400 border-red-100 dark:border-red-800'
              }`}
          >
            {selectedClient ? '已选中客户' : '未选中客户'}
          </span>
          <span className="px-3 py-1 bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 text-xs rounded-full border border-slate-200 dark:border-slate-700">
            等待AI分析
          </span>
        </div>
        {/* <button
          onClick={() => setIsDarkMode(!isDarkMode)}
          className="p-2 text-slate-400 dark:text-slate-500 hover:text-brand dark:hover:text-brand-400 hover:bg-brand-light dark:hover:bg-brand-900/30 rounded-xl transition-all"
        >
          {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button> */}
      </div>
    </div>
  )
}
