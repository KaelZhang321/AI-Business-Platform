import React from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { DndContext, closestCenter, type DragEndEvent } from '@dnd-kit/core';
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable';
import { Plus, Sparkles } from 'lucide-react';
import { AI_CARDS_DATA, SortableCard } from '../../AICards';
import { AssistantMessageContent } from '../../json-render/AssistantMessageContent';
import { EditableLayoutTag } from './EditableLayoutTag';
import type { AIResultItem, CustomerRecord, SavedLayout } from './types';

/** 主内容面板组件属性 */
interface MainContentPanelProps {
  /** 中间列样式类 */
  middleColClass: string;
  /** 右侧洞察面板是否展开 */
  isRightPanelOpen: boolean;
  /** 当前选中客户 */
  selectedCustomer: CustomerRecord | null;
  /** 当前客户的已保存布局列表 */
  currentCustomerLayouts: SavedLayout[];
  /** 拖拽约束容器引用 */
  constraintsRef: React.RefObject<HTMLDivElement | null>;
  /** 重命名布局 */
  onRenameLayout: (id: string, newName: string) => Promise<void> | void;
  /** 应用布局 */
  onApplyLayout: (id: string) => void;
  /** 删除布局 */
  onDeleteLayout: (id: string) => Promise<void> | void;
  /** 打开客户选择弹窗 */
  onOpenCustomerModal: () => void;
  /** 跳转 AI 报告对比页 */
  onNavigateToComparison: () => void;
  /** 跳转四象限评估页 */
  onNavigateToFourQuadrant: () => void;
  /** 当前展示的卡片 ID 列表 */
  dashboardCards: string[];
  /** 拖拽传感器配置 */
  dndSensors: any;
  /** 拖拽结束回调 */
  onDragEnd: (event: DragEndEvent) => void;
  /** 放大卡片 */
  onExpandCard: (id: string) => void;
  /** 删除卡片 */
  onDeleteCard: (id: string) => void;
  /** AI 分析结果列表 */
  aiResults: AIResultItem[];
  /** 最新一条 AI 助手回复内容 */
  latestAssistantMessage: string | null;
  /** 是否启用布局视图模式 */
  isLayoutViewEnabled: boolean;
  /** 各卡片的运行时数据 */
  runtimeDataByCardId: Record<string, unknown>;
  /** 各卡片的加载状态 */
  runtimeStatusByCardId: Record<string, 'loading' | 'ready' | 'empty' | 'error'>;
  /** 各卡片的错误信息 */
  runtimeErrorByCardId: Record<string, string>;
  /** 卡片触发运行时保存（用于 mutation 接口） */
  onRuntimeCardSave?: (cardId: string, payload: Record<string, unknown>) => Promise<void> | void;
}

/** 主内容面板组件：展示客户信息头部、布局标签、AI 结果卡片和拖拽排序工作区 */
export const MainContentPanel: React.FC<MainContentPanelProps> = ({
  middleColClass,
  isRightPanelOpen,
  selectedCustomer,
  currentCustomerLayouts,
  constraintsRef,
  onRenameLayout,
  onApplyLayout,
  onDeleteLayout,
  onOpenCustomerModal,
  onNavigateToComparison,
  onNavigateToFourQuadrant,
  dashboardCards,
  dndSensors,
  onDragEnd,
  onExpandCard,
  onDeleteCard,
  aiResults,
  latestAssistantMessage,
  isLayoutViewEnabled,
  runtimeDataByCardId,
  runtimeStatusByCardId,
  runtimeErrorByCardId,
  onRuntimeCardSave,
}) => {
  const hasConversationOutput = Boolean(latestAssistantMessage) && aiResults.length > 0;
  const showConversationOutputOnly = hasConversationOutput && !isLayoutViewEnabled;
  const showLayoutCards = isLayoutViewEnabled && dashboardCards.length > 0;

  return (
    <div className={`col-span-1 ${middleColClass} flex h-full min-h-0 flex-col ${!isRightPanelOpen ? '2xl:pr-[72px]' : ''}`}>
      <div className="flex flex-1 min-h-0 flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm transition-colors duration-300 dark:border-slate-700 dark:bg-slate-900">
        {!selectedCustomer ? (
          <div className="flex flex-col gap-4 border-b border-slate-100 p-6 dark:border-slate-800 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex items-start space-x-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-slate-800">
                <Plus className="h-5 w-5" />
              </div>
              <div>
                <div className="mb-1 flex items-center space-x-3">
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white">请选择客户开始 AI 工作台</h3>
                  <span className="rounded bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-500">仅支持权限内客户</span>
                </div>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  先从顶部搜索框中选择确定客户，系统才会同步客户档案、方案信息与固定 AI 分析卡。
                </p>
              </div>
            </div>
            <button
              onClick={onOpenCustomerModal}
              className="w-full whitespace-nowrap rounded-full bg-blue-500 px-6 py-2.5 text-sm font-bold text-white shadow-lg shadow-blue-500/20 transition-all hover:bg-blue-600 sm:w-auto"
            >
              去选择客户
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-4 border-b border-slate-100 p-6 dark:border-slate-800 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-purple-100 text-xl font-bold text-purple-600 dark:bg-purple-900/40 dark:text-purple-400">
                {selectedCustomer.name.charAt(0)}
              </div>
              <div>
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <span className="text-lg font-bold text-slate-900 dark:text-white">{selectedCustomer.name} · VIP会员</span>
                  <span className="rounded-full bg-purple-50 px-2 py-0.5 text-[10px] font-bold uppercase text-purple-600">VIP</span>
                </div>
                <div className="text-xs text-slate-500 dark:text-slate-400">
                  {selectedCustomer.age}岁 · {selectedCustomer.gender} · 当前在管方案2个 · 最近30天沟通下降 · 仅看我负责客户
                </div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={onNavigateToComparison}
                className="rounded-full bg-blue-500 px-4 py-1.5 text-xs font-bold text-white shadow-sm transition-all hover:bg-blue-600"
              >
                AI报告对比
              </button>
              <button
                onClick={onNavigateToFourQuadrant}
                className="rounded-full bg-purple-500 px-4 py-1.5 text-xs font-bold text-white shadow-sm transition-all hover:bg-purple-600"
              >
                四象限健康评估
              </button>
            </div>
          </div>
        )}

        {selectedCustomer && currentCustomerLayouts.length > 0 && (
          <div className="group relative overflow-hidden border-b border-slate-100 bg-slate-50/50 dark:border-slate-800 dark:bg-slate-800/20">
            <div className="flex items-center px-6 py-3">
              <div className="relative flex-1 overflow-x-auto custom-scrollbar" ref={constraintsRef}>
                <div className="flex min-w-full w-max space-x-3 px-2 pb-1">
                  {currentCustomerLayouts.map((layout) => (
                    <motion.div
                      key={layout.id}
                      drag="x"
                      dragConstraints={constraintsRef}
                      dragElastic={0.2}
                      dragMomentum
                      className="shrink-0 cursor-grab active:cursor-grabbing"
                    >
                      <EditableLayoutTag
                        layout={layout}
                        onRename={onRenameLayout}
                        onApply={onApplyLayout}
                        onDelete={onDeleteLayout}
                      />
                    </motion.div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="flex flex-1 min-h-0 flex-col p-6">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">AI结果显示区</h3>
            {!selectedCustomer ? (
              <span className="rounded-full bg-red-50 px-3 py-1 text-[10px] font-medium text-red-500">待客户激活</span>
            ) : (
              <span className="rounded-full bg-green-50 px-3 py-1 text-[10px] font-medium text-green-600">客户信息已同步</span>
            )}
          </div>

          {!selectedCustomer ? (
            <div className="flex flex-1 flex-col items-center justify-center rounded-3xl border-2 border-dashed border-slate-200 bg-slate-50/50 p-12 text-center dark:border-slate-700 dark:bg-slate-800/30">
              <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-blue-50 text-2xl font-bold text-blue-500 dark:bg-blue-900/30">客</div>
              <h4 className="mb-3 text-xl font-bold text-slate-900 dark:text-white">请先选择确定客户</h4>
              <p className="mb-12 max-w-md text-sm leading-relaxed text-slate-500 dark:text-slate-400">
                客户确定后，系统会同步客户基本信息与方案信息；左侧继续和小智对话后，这里开始展示 AI 生成结果。
              </p>

              <div className="grid w-full max-w-2xl grid-cols-1 gap-6 md:grid-cols-3">
                <div className="rounded-2xl border border-slate-100 bg-white p-5 text-left shadow-sm dark:border-slate-700 dark:bg-slate-800">
                  <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-blue-500 font-bold text-white">1</div>
                  <div className="mb-1 font-bold text-slate-900 dark:text-white">选择客户</div>
                  <div className="text-xs text-slate-500">同步客户上下文</div>
                </div>
                <div className="rounded-2xl border border-slate-100 bg-white p-5 text-left shadow-sm dark:border-slate-700 dark:bg-slate-800">
                  <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-purple-500 font-bold text-white">2</div>
                  <div className="mb-1 font-bold text-slate-900 dark:text-white">与小智对话</div>
                  <div className="text-xs text-slate-500">提出分析问题</div>
                </div>
                <div className="rounded-2xl border border-slate-100 bg-white p-5 text-left shadow-sm dark:border-slate-700 dark:bg-slate-800">
                  <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-green-500 font-bold text-white">3</div>
                  <div className="mb-1 font-bold text-slate-900 dark:text-white">生成结果卡</div>
                  <div className="text-xs text-slate-500">在这里展示 AI 输出</div>
                </div>
              </div>
            </div>
          ) : (
            <div className="custom-scrollbar flex flex-1 min-h-0 flex-col space-y-6 overflow-y-auto pb-6 pr-2">
              {showConversationOutputOnly && (
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="dark:border-blue-900/30 dark:bg-blue-900/10"
                >
                  {/* <div className="mb-3 flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-blue-500" />
                    <h4 className="text-sm font-bold text-slate-900 dark:text-white">AI结构化结果</h4>
                    <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-600 dark:bg-blue-900/40 dark:text-blue-300">
                      最新回复
                    </span>
                  </div> */}
                  <div>
                    <AssistantMessageContent content={latestAssistantMessage} />
                  </div>
                  <p className="mt-3 text-[11px] text-slate-500 dark:text-slate-400">
                    点击上方布局标签可切换回默认卡片展示。
                  </p>
                </motion.div>
              )}

              {showLayoutCards ? (
                <DndContext sensors={dndSensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                  <SortableContext items={dashboardCards} strategy={rectSortingStrategy}>
                    <div className="flex flex-wrap gap-6">
                      {dashboardCards.map((id) => {
                        const cardData = AI_CARDS_DATA.find((card) => card.id === id);
                        if (!cardData) {
                          return null;
                        }
                        const CardComponent = cardData.component;
                        return (
                          <SortableCard
                            key={id}
                            id={id}
                            title={cardData.title}
                            colSpan={cardData.colSpan}
                            onEnlarge={() => onExpandCard(id)}
                            onDelete={() => onDeleteCard(id)}
                          >
                            <CardComponent
                              runtimeData={runtimeDataByCardId[id]}
                              runtimeDataByCardId={runtimeDataByCardId}
                              runtimeStatus={runtimeStatusByCardId[id]}
                              runtimeError={runtimeErrorByCardId[id]}
                              onRuntimeSave={(payload: Record<string, unknown>) => {
                                void onRuntimeCardSave?.(id, payload);
                              }}
                            />
                          </SortableCard>
                        );
                      })}
                    </div>
                  </SortableContext>
                </DndContext>
              ) : showConversationOutputOnly ? null : aiResults.length > 0 ? (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <AnimatePresence>
                    {aiResults.map((result) => (
                      <motion.div
                        key={result.id}
                        initial={{ opacity: 0, y: 20, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800"
                      >
                        <div className="mb-4 flex items-center space-x-2">
                          <Sparkles className="h-5 w-5 text-blue-500" />
                          <h4 className="font-bold text-slate-900 dark:text-white">{result.title}</h4>
                        </div>
                        <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">{result.content}</p>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
                //   ) : (
                //   <>
                //     <div className="flex flex-1 flex-col items-center justify-center rounded-3xl border-2 border-dashed border-slate-200 bg-slate-50/50 p-12 text-center dark:border-slate-700 dark:bg-slate-800/30">
                //       <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-blue-50 text-2xl font-bold text-blue-500 dark:bg-blue-900/30">AI</div>
                //       <h4 className="mb-3 text-xl font-bold text-slate-900 dark:text-white">已同步客户与方案信息，等待你与小智对话</h4>
                //       <p className="mb-8 max-w-md text-sm leading-relaxed text-slate-500 dark:text-slate-400">
                //         当你在左侧对话框向小智提问后，AI 会在这里生成摘要卡、建议卡、话术卡等结果。
                //       </p>
                //       <button className="rounded-full bg-blue-500 px-6 py-2.5 text-sm font-bold text-white shadow-lg shadow-blue-500/20 transition-all hover:bg-blue-600">
                //         试着问：给出续费建议
                //       </button>
                //     </div>

                //     <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                //       <div className="rounded-2xl border border-slate-100 bg-slate-50 p-5 dark:border-slate-700 dark:bg-slate-800/50">
                //         <div className="mb-2 font-bold text-slate-700 dark:text-slate-300">示例结果卡：客户全景摘要</div>
                //         <div className="text-xs text-slate-500">展示客户当前价值、活跃状态、核心风险与沟通要点。</div>
                //       </div>
                //       <div className="rounded-2xl border border-slate-100 bg-slate-50 p-5 dark:border-slate-700 dark:bg-slate-800/50">
                //         <div className="mb-2 font-bold text-slate-700 dark:text-slate-300">示例结果卡：行动建议</div>
                //         <div className="text-xs text-slate-500">展示续费、升单、回访、预警处理等下一步动作建议。</div>
                //       </div>
                //     </div>

                //     <div className="rounded-2xl border border-slate-100 bg-slate-50 p-5 dark:border-slate-700 dark:bg-slate-800/50">
                //       <div className="mb-3 text-sm font-bold text-blue-500">推荐对话起点</div>
                //       <ol className="list-inside list-decimal space-y-2 text-sm text-slate-600 dark:text-slate-400">
                //         <li>总结客户近期经营重点</li>
                //         <li>判断未来6个月消费趋势</li>
                //         <li>生成续费与升单策略</li>
                //       </ol>
                //     </div>
                //   </>
                // )}
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
