import { useState } from 'react'
import { Check, Loader2, Plus, X } from 'lucide-react'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { useDroppable } from '@dnd-kit/core'
import { SortableItem } from './SortableItem'
import type { QuadrantItem } from '../types'

interface QuadrantPanelProps {
  id: string
  title: string
  items: QuadrantItem[]
  colorTheme: 'amber' | 'red' | 'blue' | 'orange'
  onRemoveItem: (id: string) => void
  onAddItem: (content: string, category?: string) => void
  isAnalyzing: boolean
  hasResult: boolean
}

const themeClasses = {
  amber: {
    bg: 'bg-[#FFFBEB] dark:bg-amber-900/10',
    border: 'border-amber-100 dark:border-amber-900/30',
    text: 'text-amber-600 dark:text-amber-500',
    btnBorder: 'border-amber-500',
    btnText: 'text-amber-600',
    itemColor: 'border-amber-100/50 dark:border-amber-800/30 hover:border-amber-200',
    handleColor: 'text-amber-400',
    iconColor: 'text-amber-500',
  },
  red: {
    bg: 'bg-[#FEF2F2] dark:bg-red-900/10',
    border: 'border-red-100 dark:border-red-900/30',
    text: 'text-red-500 dark:text-red-400',
    btnBorder: 'border-red-500',
    btnText: 'text-red-500',
    itemColor: 'border-red-100/50 dark:border-red-800/30 hover:border-red-200',
    handleColor: 'text-red-400',
    iconColor: 'text-red-500',
  },
  blue: {
    bg: 'bg-[#EFF6FF] dark:bg-blue-900/10',
    border: 'border-blue-100 dark:border-blue-900/30',
    text: 'text-blue-600 dark:text-blue-500',
    btnBorder: 'border-blue-500',
    btnText: 'text-blue-600',
    itemColor: 'border-blue-100/50 dark:border-blue-800/30 hover:border-blue-200',
    handleColor: 'text-blue-400',
    iconColor: 'text-blue-500',
  },
  orange: {
    bg: 'bg-[#FFF7ED] dark:bg-orange-900/10',
    border: 'border-orange-100 dark:border-orange-900/30',
    text: 'text-orange-600 dark:text-orange-500',
    btnBorder: 'border-orange-500',
    btnText: 'text-orange-600',
    itemColor: 'border-orange-100/50 dark:border-orange-800/30 hover:border-orange-200',
    handleColor: 'text-orange-400',
    iconColor: 'text-orange-500',
  },
}

export const QuadrantPanel = ({
  id,
  title,
  items,
  colorTheme,
  onRemoveItem,
  onAddItem,
  isAnalyzing,
  hasResult,
}: QuadrantPanelProps) => {
  const [newItemContent, setNewItemContent] = useState('')
  const [isAdding, setIsAdding] = useState(false)
  const { setNodeRef } = useDroppable({ id })
  const theme = themeClasses[colorTheme]

  const handleAdd = () => {
    if (!newItemContent.trim()) return
    onAddItem(newItemContent.trim())
    setNewItemContent('')
    setIsAdding(false)
  }

  return (
    <div ref={setNodeRef} className={`rounded-2xl p-5 border flex flex-col overflow-hidden cursor-target ${theme.bg} ${theme.border}`}>
      <div className="flex items-center justify-between mb-4 shrink-0">
        <h4 className={`font-bold text-lg ${theme.text}`}>{title}</h4>
        {hasResult && (
          <button
            onClick={() => setIsAdding(true)}
            className={`px-4 py-1.5 text-xs rounded-full border bg-white dark:bg-slate-800 flex items-center ${theme.btnBorder} ${theme.btnText}`}
          >
            <Plus className="w-3 h-3 mr-1" />
            添加
          </button>
        )}
      </div>

      <div className="flex-1 flex flex-col overflow-y-auto custom-scrollbar pr-1">
        {isAnalyzing ? (
          <div className="flex flex-col items-center justify-center h-full space-y-2 opacity-50">
            <Loader2 className={`w-6 h-6 animate-spin ${theme.iconColor}`} />
            <p className={`text-xs ${theme.text}`}>处理中...</p>
          </div>
        ) : hasResult ? (
          <div className="flex flex-col h-full">
            {isAdding && (
              <div className="mb-3 flex flex-col space-y-2 bg-white dark:bg-slate-800 p-2 rounded-xl border shadow-sm">
                <div className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={newItemContent}
                    onChange={(e) => setNewItemContent(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
                    placeholder="输入新项..."
                    className="flex-1 px-2 py-1 text-sm border-none bg-transparent text-slate-900 dark:text-white focus:outline-none focus:ring-0"
                    autoFocus
                  />
                  <button onClick={handleAdd} className="p-1.5 text-green-600 hover:bg-green-50 rounded-lg">
                    <Check className="w-4 h-4" />
                  </button>
                  <button onClick={() => setIsAdding(false)} className="p-1.5 text-slate-400 hover:bg-slate-100 rounded-lg">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}

            <SortableContext id={id} items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
              <div className="flex-1 min-h-[50px]">
                {items.map((item, index) => {
                  const prevItem = items[index - 1]
                  const showAbnormalHeader = item.category === 'abnormal' && prevItem?.category !== 'abnormal'
                  const showRecommendationHeader =
                    item.category === 'recommendation' && prevItem?.category !== 'recommendation'

                  return (
                    <div key={item.id}>
                      {showAbnormalHeader && (
                        <div className={`text-xs font-bold mb-2 ${index > 0 ? 'mt-4' : ''} flex items-center ${theme.text}`}>
                          <div className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current" />
                          异常指标
                        </div>
                      )}
                      {showRecommendationHeader && (
                        <div className={`text-xs font-bold mb-2 ${index > 0 ? 'mt-4' : ''} flex items-center ${theme.text}`}>
                          <div className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current" />
                          推荐方案
                        </div>
                      )}
                      <SortableItem
                        id={item.id}
                        content={item.content}
                        onRemove={onRemoveItem}
                        colorClass={theme.itemColor}
                        handleColorClass={theme.handleColor}
                      />
                    </div>
                  )
                })}
              </div>
            </SortableContext>
          </div>
        ) : (
          <div className="flex flex-col justify-center items-center h-full text-center px-4 bg-white/50 dark:bg-slate-800/30 rounded-xl border border-white/50 dark:border-slate-700/30">
            <h5 className="text-slate-500 dark:text-slate-400 font-bold mb-1 text-sm">等待 AI 填充</h5>
            <p className="text-xs text-slate-400 dark:text-slate-500">完成选择后，可补充备注给 AI 进一步校准。</p>
          </div>
        )}
      </div>
    </div>
  )
}
