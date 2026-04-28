import { useRef, useState, type Dispatch, type SetStateAction } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { GripVertical, Loader2, Maximize2, X } from 'lucide-react'
import type { DragEndEvent, DragOverEvent, DragStartEvent } from '@dnd-kit/core'
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { arrayMove, sortableKeyboardCoordinates } from '@dnd-kit/sortable'
import { QuadrantPanel } from './QuadrantPanel'
import type { QuadrantData, QuadrantKey } from '../types'

interface QuadrantWorkspaceProps {
  showResults: boolean
  isAnalyzing: boolean
  isEnlarged: boolean
  setIsEnlarged: (value: boolean) => void
  quadrantData: QuadrantData
  setQuadrantData: Dispatch<SetStateAction<QuadrantData>>
  analysisStep: string
  analysisProgress: number
  onQuadrantAddItem?: (payload: {
    quadrantKey: QuadrantKey
    content: string
    category?: string
    nextData: QuadrantData
  }) => void
  onQuadrantDragEnd?: (nextData: QuadrantData) => void
}

export const QuadrantWorkspace = ({
  showResults,
  isAnalyzing,
  isEnlarged,
  setIsEnlarged,
  quadrantData,
  setQuadrantData,
  analysisStep,
  analysisProgress,
  onQuadrantAddItem,
  onQuadrantDragEnd,
}: QuadrantWorkspaceProps) => {
  const [activeId, setActiveId] = useState<string | null>(null)
  const lastOverItemIdRef = useRef<string | null>(null)

  const inferGroupByIndex = (items: Array<{ category?: string }>, index: number): 'abnormal' | 'recommendation' => {
    const current = items[index]
    if (!current) {
      return 'abnormal'
    }

    if (current.category === 'recommendation') {
      return 'recommendation'
    }
    if (current.category === 'abnormal') {
      return 'abnormal'
    }

    const firstRecommendationIndex = items.findIndex((item) => item.category === 'recommendation')
    if (firstRecommendationIndex >= 0 && index >= firstRecommendationIndex) {
      return 'recommendation'
    }

    return 'abnormal'
  }

  const getGroupedInsertIndex = (items: Array<{ category?: string }>, group: 'abnormal' | 'recommendation') => {
    if (group === 'abnormal') {
      const firstRecommendationIndex = items.findIndex((_, index) => inferGroupByIndex(items, index) === 'recommendation')
      return firstRecommendationIndex >= 0 ? firstRecommendationIndex : items.length
    }

    const lastRecommendationIndex = [...items]
      .map((item, index) => ({ item, index }))
      .reverse()
      .find(({ index }) => inferGroupByIndex(items, index) === 'recommendation')?.index

    return typeof lastRecommendationIndex === 'number' ? lastRecommendationIndex + 1 : items.length
  }

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  )

  const findContainer = (id: string) => {
    if (id in quadrantData) {
      return id as QuadrantKey
    }
    return (Object.keys(quadrantData) as QuadrantKey[]).find((key) => quadrantData[key].some((item) => item.id === id))
  }

  const handleRemoveItem = (containerId: QuadrantKey, itemId: string) => {
    setQuadrantData((prev) => ({
      ...prev,
      [containerId]: prev[containerId].filter((item) => item.id !== itemId),
    }))
  }

  const handleAddItem = (containerId: QuadrantKey, content: string, category?: string) => {
    const newItem = { id: `new-${Date.now()}`, content, category }
    const currentItems = quadrantData[containerId]

    let nextItems: typeof currentItems

    if (!category) {
      nextItems = [newItem, ...currentItems]
    } else {
      const groupIndexes = currentItems.reduce<number[]>((acc, item, index) => {
        if (item.category === category) {
          acc.push(index)
        }
        return acc
      }, [])

      if (groupIndexes.length === 0) {
        nextItems = [newItem, ...currentItems]
      } else {
        const insertIndex = groupIndexes[groupIndexes.length - 1] + 1
        nextItems = [...currentItems]
        nextItems.splice(insertIndex, 0, newItem)
      }
    }

    const nextData: QuadrantData = {
      ...quadrantData,
      [containerId]: nextItems,
    }

    setQuadrantData(nextData)
    onQuadrantAddItem?.({ quadrantKey: containerId, content, category, nextData })
  }

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(String(event.active.id))
    lastOverItemIdRef.current = null
  }

  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event
    if (!over) return

    const overId = String(over.id)
    if (!(overId in quadrantData)) {
      lastOverItemIdRef.current = overId
    }

    const activeContainer = findContainer(String(active.id))
    const overContainer = findContainer(overId) || (overId as QuadrantKey)

    if (!activeContainer || !overContainer || activeContainer === overContainer) {
      return
    }

    setQuadrantData((prev) => {
      const activeItems = prev[activeContainer]
      const overItems = prev[overContainer]

      const activeIndex = activeItems.findIndex((item) => item.id === String(active.id))
      if (activeIndex < 0) {
        return prev
      }

      const movingGroup = inferGroupByIndex(activeItems, activeIndex)

      let overIndex = overItems.length

      if (over.id in prev) {
        const hasSameGroupInTarget = overItems.some((item, index) => inferGroupByIndex(overItems, index) === movingGroup)
        if (overItems.length > 0 && !hasSameGroupInTarget) {
          return prev
        }
        overIndex = getGroupedInsertIndex(overItems, movingGroup)
      } else {
        const overTargetIndex = overItems.findIndex((item) => item.id === String(over.id))
        if (overTargetIndex < 0) {
          return prev
        }

        const overTargetGroup = inferGroupByIndex(overItems, overTargetIndex)
        if (overTargetGroup !== movingGroup) {
          return prev
        }

        overIndex = overTargetIndex
      }

      const newActiveItems = [...activeItems]
      const [itemToMove] = newActiveItems.splice(activeIndex, 1)

      const newOverItems = [...overItems]
      newOverItems.splice(overIndex >= 0 ? overIndex : newOverItems.length, 0, itemToMove)

      return {
        ...prev,
        [activeContainer]: newActiveItems,
        [overContainer]: newOverItems,
      }
    })
  }

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    setActiveId(null)

    if (!over) return

    const activeContainer = findContainer(String(active.id))
    const overId = String(over.id)
    const overContainer = findContainer(overId) || (overId as QuadrantKey)

    if (!activeContainer || !overContainer) {
      return
    }

    if (activeContainer !== overContainer) {
      const activeItems = quadrantData[activeContainer]
      const overItems = quadrantData[overContainer]
      const activeIndex = activeItems.findIndex((item) => item.id === String(active.id))
      const overIndex = overItems.findIndex((item) => item.id === overId)
      const movingItem = activeIndex >= 0 ? activeItems[activeIndex] : null
      const overItem = overIndex >= 0 ? overItems[overIndex] : null
      const movingGroup = movingItem ? inferGroupByIndex(activeItems, activeIndex) : null
      const overGroup = overItem ? inferGroupByIndex(overItems, overIndex) : null

      if (movingGroup && overGroup && movingGroup !== overGroup) {
        return
      }

      // 跨象限移动在 onDragOver 已写入状态，这里只负责落点后统一触发保存
      onQuadrantDragEnd?.(quadrantData)
      return
    }

    const items = quadrantData[activeContainer]
    const oldIndex = items.findIndex((item) => item.id === String(active.id))
    let targetOverId = overId
    if (targetOverId in quadrantData && lastOverItemIdRef.current) {
      const lastOverContainer = findContainer(lastOverItemIdRef.current)
      if (lastOverContainer === overContainer) {
        targetOverId = lastOverItemIdRef.current
      }
    }

    const newIndex = targetOverId in quadrantData ? oldIndex : items.findIndex((item) => item.id === targetOverId)
    if (oldIndex < 0 || newIndex < 0) {
      return
    }

    const newItems = oldIndex !== newIndex ? arrayMove(items, oldIndex, newIndex) : [...items]
    const movedItem = { ...newItems[newIndex] }
    const itemAbove = newIndex > 0 ? newItems[newIndex - 1] : null

    let categoryChanged = false
    if (itemAbove && itemAbove.category && movedItem.category !== itemAbove.category) {
      movedItem.category = itemAbove.category
      categoryChanged = true
    }

    if (oldIndex !== newIndex || categoryChanged) {
      newItems[newIndex] = movedItem
    }

    const nextData: QuadrantData = {
      ...quadrantData,
      [activeContainer]: newItems,
    }

    setQuadrantData((prev) => {
      if (oldIndex !== newIndex || categoryChanged) {
        return {
          ...prev,
          [activeContainer]: newItems,
        }
      }
      return prev
    })

    onQuadrantDragEnd?.(nextData)
    lastOverItemIdRef.current = null
  }

  const getActiveItemContent = () => {
    if (!activeId) return null
    for (const key of Object.keys(quadrantData) as QuadrantKey[]) {
      const item = quadrantData[key].find((i) => i.id === activeId)
      if (item) return item.content
    }
    return null
  }

  return (
    <>
      {isEnlarged && <div className="fixed inset-0 z-40 bg-slate-900/60 backdrop-blur-sm" onClick={() => setIsEnlarged(false)} />}
      <div
        className={
          isEnlarged
            ? 'fixed inset-6 z-50 bg-white dark:bg-slate-800 rounded-3xl shadow-2xl p-8 flex flex-col overflow-hidden'
            : 'bg-white dark:bg-slate-800 rounded-2xl p-6 shadow-sm border border-slate-100 dark:border-slate-700 flex-1 flex flex-col overflow-hidden relative quadrants-container cursor-none'
        }
      >
        <div className="flex items-center justify-between mb-6 shrink-0">
          <h3 className="text-xl font-bold text-slate-900 dark:text-white">AI四象限结果</h3>
          {showResults && (
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setIsEnlarged(!isEnlarged)}
                className="px-4 py-2 bg-slate-800 text-slate-200 border border-slate-700 text-sm font-bold rounded-full hover:bg-slate-700 transition-colors flex items-center"
              >
                {isEnlarged ? (
                  <>
                    <X className="w-4 h-4 mr-1.5" />
                    退出放大
                  </>
                ) : (
                  <>
                    <Maximize2 className="w-4 h-4 mr-1.5" />
                    放大预览
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        <div className="flex-1 min-h-0 relative">
          <AnimatePresence>
            {isAnalyzing && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 z-20 bg-white/60 dark:bg-slate-800/60 backdrop-blur-[2px] flex flex-col items-center justify-center pointer-events-none"
              >
                <motion.div
                  initial={{ top: '0%' }}
                  animate={{ top: '100%' }}
                  transition={{ duration: 2.5, repeat: Infinity, ease: 'linear' }}
                  className="absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-brand to-transparent shadow-[0_0_15px_rgba(var(--brand-rgb),0.5)] z-30"
                />
                <div className="relative">
                  <motion.div
                    animate={{ scale: [1, 1.2, 1], opacity: [0.2, 0.5, 0.2] }}
                    transition={{ duration: 2, repeat: Infinity }}
                    className="absolute inset-0 bg-brand/30 rounded-full blur-3xl"
                  />
                  <div className="relative bg-white dark:bg-slate-800 p-8 rounded-[2.5rem] shadow-2xl border border-brand/20 flex flex-col items-center space-y-6 max-w-xs w-full">
                    <div className="relative">
                      <Loader2 className="w-16 h-16 text-brand animate-spin" />
                      <motion.div
                        animate={{ opacity: [0.5, 1, 0.5] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                        className="absolute inset-0 flex items-center justify-center"
                      >
                        <div className="w-2 h-2 bg-brand rounded-full" />
                      </motion.div>
                    </div>
                    <div className="text-center space-y-2">
                      <p className="text-xl font-black text-slate-900 dark:text-white tracking-tight">AI 深度分析中</p>
                      <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">{analysisStep}</p>
                    </div>
                    <div className="w-full space-y-2">
                      <div className="flex justify-between text-[10px] font-bold text-brand uppercase tracking-widest">
                        <span>Progress</span>
                        <span>{Math.round(analysisProgress)}%</span>
                      </div>
                      <div className="w-full h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden p-0.5">
                        <motion.div
                          className="h-full bg-brand rounded-full shadow-[0_0_10px_rgba(var(--brand-rgb),0.3)]"
                          initial={{ width: 0 }}
                          animate={{ width: `${analysisProgress}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDragEnd={handleDragEnd}
          >
            <div className="grid grid-cols-2 gap-6 h-full">
              <QuadrantPanel
                id="intervention"
                title="A级-红色健康预警"
                items={quadrantData.intervention}
                colorTheme="red"
                onRemoveItem={(id) => handleRemoveItem('intervention', id)}
                onAddItem={(content, category) => handleAddItem('intervention', content, category)}
                isAnalyzing={isAnalyzing}
                hasResult={showResults}
              />
              <QuadrantPanel
                id="monitoring"
                title="B级-橙色健康预警"
                items={quadrantData.monitoring}
                colorTheme="orange"
                onRemoveItem={(id) => handleRemoveItem('monitoring', id)}
                onAddItem={(content, category) => handleAddItem('monitoring', content, category)}
                isAnalyzing={isAnalyzing}
                hasResult={showResults}
              />
              <QuadrantPanel
                id="prevention"
                title="C级-黄色健康预警"
                items={quadrantData.prevention}
                colorTheme="amber"
                onRemoveItem={(id) => handleRemoveItem('prevention', id)}
                onAddItem={(content, category) => handleAddItem('prevention', content, category)}
                isAnalyzing={isAnalyzing}
                hasResult={showResults}
              />
              <QuadrantPanel
                id="maintenance"
                title="D级-蓝色健康预警"
                items={quadrantData.maintenance}
                colorTheme="blue"
                onRemoveItem={(id) => handleRemoveItem('maintenance', id)}
                onAddItem={(content, category) => handleAddItem('maintenance', content, category)}
                isAnalyzing={isAnalyzing}
                hasResult={showResults}
              />
            </div>

            <DragOverlay>
              {activeId ? (
                <div className="flex items-center justify-between p-2 bg-white dark:bg-slate-800 rounded-lg border shadow-lg opacity-90 scale-105">
                  <div className="flex items-center flex-1 min-w-0">
                    <div className="p-1 mr-1 text-slate-400">
                      <GripVertical className="w-4 h-4" />
                    </div>
                    <span className="text-sm text-slate-700 dark:text-slate-200 truncate">{getActiveItemContent()}</span>
                  </div>
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>
        </div>
      </div>
    </>
  )
}
