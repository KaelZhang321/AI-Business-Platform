import React from 'react';
import { ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';
import type { CustomerRecord } from './types';

interface InsightsAreaProps {
  isRightPanelOpen: boolean;
  selectedCustomer: CustomerRecord | null;
  onOpenPanel: () => void;
  onClosePanel: () => void;
}

export const InsightsArea: React.FC<InsightsAreaProps> = ({
  isRightPanelOpen,
  selectedCustomer,
  onOpenPanel,
  onClosePanel,
}) => {
  return (
    <>
      {!isRightPanelOpen && (
        <div className="fixed bottom-8 right-6 z-40 flex items-center 2xl:absolute 2xl:bottom-auto 2xl:right-0 2xl:top-1/2 2xl:-translate-y-1/2">
          <button
            onClick={onOpenPanel}
            className="absolute -left-12 z-10 flex w-10 flex-col items-center justify-center rounded-full border border-slate-200 bg-white py-4 shadow-lg transition-colors hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700"
          >
            <ChevronLeft className="mb-1 h-5 w-5 text-slate-600 dark:text-slate-300" />
            <span className="text-xs font-bold text-slate-600 dark:text-slate-300">开</span>
          </button>

          <div className="flex flex-col items-center space-y-6 rounded-full border border-slate-200 bg-white px-2 py-6 shadow-xl dark:border-slate-700 dark:bg-slate-800">
            <span className="text-sm font-bold text-slate-400">AI</span>

            <div className="flex flex-col space-y-5">
              <div
                className="relative flex h-12 w-12 cursor-pointer items-center justify-center rounded-full bg-blue-50 transition-transform hover:scale-110 dark:bg-blue-900/30"
                onClick={onOpenPanel}
                title="AI消耗预测"
              >
                <span className="text-xl font-bold text-blue-500">¥</span>
                <div className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full border border-slate-100 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
                  <span className="text-[10px] font-bold text-slate-600 dark:text-slate-300">6</span>
                </div>
              </div>

              <div
                className="relative flex h-12 w-12 cursor-pointer items-center justify-center rounded-full bg-purple-50 transition-transform hover:scale-110 dark:bg-purple-900/30"
                onClick={onOpenPanel}
                title="AI生单潜力"
              >
                <span className="text-xl font-bold text-purple-500">升</span>
                <div className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full border border-slate-100 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
                  <span className="text-[10px] font-bold text-slate-600 dark:text-slate-300">高</span>
                </div>
              </div>

              <div
                className="relative flex h-12 w-12 cursor-pointer items-center justify-center rounded-full bg-red-50 transition-transform hover:scale-110 dark:bg-red-900/30"
                onClick={onOpenPanel}
                title="AI风险预警"
              >
                <span className="text-xl font-bold text-red-500">!</span>
                <div className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full border border-slate-100 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
                  <span className="text-[10px] font-bold text-slate-600 dark:text-slate-300">中</span>
                </div>
              </div>
            </div>

            <div className="mt-2 h-2 w-2 rounded-full bg-slate-200 dark:bg-slate-700" />
          </div>
        </div>
      )}

      {isRightPanelOpen && (
        <div className="col-span-1 flex min-h-0 flex-col 2xl:col-span-3">
          <div className="flex items-center justify-between p-5 transition-colors duration-300">
            <div className="flex items-center space-x-2">
              <Sparkles className="h-5 w-5 text-purple-500" />
              <h3 className="font-bold text-slate-900 dark:text-white">AI 智能洞察</h3>
            </div>
            <button
              onClick={onClosePanel}
              className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-300"
              title="收起洞察面板"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="custom-scrollbar flex flex-1 min-h-0 flex-col space-y-6 overflow-y-auto pb-6 pr-2">
            <div className="flex min-h-[250px] flex-col rounded-2xl border border-slate-200/60 bg-white/80 p-6 shadow-sm backdrop-blur-md transition-colors duration-300 dark:border-slate-700/60 dark:bg-slate-800/80">
              <div className="mb-6 flex items-center justify-between">
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">AI消耗预测</h3>
                {!selectedCustomer ? (
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-medium text-slate-500 dark:bg-slate-800">待生成</span>
                ) : (
                  <span className="rounded-full bg-green-50 px-2 py-1 text-[10px] font-medium text-green-600">6个月预测</span>
                )}
              </div>

              {!selectedCustomer ? (
                <div className="flex flex-1 flex-col items-center justify-center text-center">
                  <div className="mb-4 flex space-x-1">
                    <div className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                    <div className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                    <div className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                  </div>
                  <div className="mb-2 text-sm font-bold text-slate-700 dark:text-slate-300">选择确定客户后自动生成</div>
                  <div className="text-xs text-slate-400">当前卡片保持空白提示态，引导你先从顶部选择权限范围内的客户。</div>
                </div>
              ) : (
                <div className="relative space-y-6 before:absolute before:bottom-2 before:left-[5px] before:top-2 before:w-px before:bg-slate-200 dark:before:bg-slate-700">
                  <div className="relative pl-5">
                    <div className="absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full bg-blue-500" />
                    <div className="text-sm font-bold text-slate-800 dark:text-slate-200">4月 启动期</div>
                    <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">体检评估 + 首次中医调理</div>
                    <div className="mt-0.5 text-xs font-medium text-blue-500">预计消耗 ¥8,500</div>
                  </div>
                  <div className="relative pl-5">
                    <div className="absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full bg-blue-500" />
                    <div className="text-sm font-bold text-slate-800 dark:text-slate-200">5-6月 密集期</div>
                    <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">中医调理4次 + 光电抗衰2次</div>
                    <div className="mt-0.5 text-xs font-medium text-blue-500">预计消耗 ¥32,000</div>
                  </div>
                  <div className="relative pl-5">
                    <div className="absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full bg-green-500" />
                    <div className="text-sm font-bold text-slate-800 dark:text-slate-200">7-9月 巩固期</div>
                    <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">复查 + 维护疗程组合</div>
                    <div className="mt-0.5 text-xs font-medium text-blue-500">预计消耗 ¥27,500</div>
                  </div>
                </div>
              )}
            </div>

            <div className="flex min-h-[250px] flex-col rounded-2xl border border-slate-200/60 bg-white/80 p-6 shadow-sm backdrop-blur-md transition-colors duration-300 dark:border-slate-700/60 dark:bg-slate-800/80">
              <div className="mb-6 flex items-center justify-between">
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">AI升单潜力</h3>
                {!selectedCustomer ? (
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-medium text-slate-500 dark:bg-slate-800">待生成</span>
                ) : (
                  <span className="rounded-full bg-purple-50 px-2 py-1 text-[10px] font-medium text-purple-600">高机会</span>
                )}
              </div>

              {!selectedCustomer ? (
                <div className="flex flex-1 flex-col items-center justify-center text-center">
                  <div className="mb-4 flex space-x-1">
                    <div className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                    <div className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                    <div className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                  </div>
                  <div className="mb-2 text-sm font-bold text-slate-700 dark:text-slate-300">选择确定客户后自动生成</div>
                  <div className="text-xs text-slate-400">当前卡片保持空白提示态，引导你先从顶部选择权限范围内的客户。</div>
                </div>
              ) : (
                <>
                  <div className="mb-6 grid grid-cols-3 gap-3">
                    <div className="flex flex-col items-center justify-center rounded-2xl bg-purple-50 p-3 text-center dark:bg-purple-900/30">
                      <div className="mb-1 text-xl font-bold text-purple-600 dark:text-purple-400">高</div>
                      <div className="text-[10px] font-medium text-purple-500">升单潜力</div>
                    </div>
                    <div className="flex flex-col items-center justify-center rounded-2xl bg-blue-50 p-3 text-center dark:bg-blue-900/30">
                      <div className="mb-1 text-xl font-bold text-blue-600 dark:text-blue-400">45%</div>
                      <div className="text-[10px] font-medium text-blue-500">转化概率</div>
                    </div>
                    <div className="flex flex-col items-center justify-center rounded-2xl bg-green-50 p-3 text-center dark:bg-green-900/30">
                      <div className="mb-1 text-xl font-bold text-green-600 dark:text-green-400">¥80K</div>
                      <div className="text-[10px] font-medium text-green-500">潜在金额</div>
                    </div>
                  </div>
                  <div className="mt-auto">
                    <div className="mb-1 text-sm font-bold text-slate-800 dark:text-slate-200">推荐：中医调理金卡</div>
                    <div className="flex items-center justify-between">
                      <div className="max-w-[140px] text-[10px] leading-tight text-slate-500">AI匹配度 92% · 基于消费节奏与沟通意向分析</div>
                      <button className="rounded-full bg-blue-500 px-3 py-1.5 text-xs font-bold text-white transition-all hover:bg-blue-600">生成话术</button>
                    </div>
                  </div>
                </>
              )}
            </div>

            <div className="flex min-h-[250px] flex-col rounded-2xl border border-slate-200/60 bg-white/80 p-6 shadow-sm backdrop-blur-md transition-colors duration-300 dark:border-slate-700/60 dark:bg-slate-800/80">
              <div className="mb-6 flex items-center justify-between">
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">AI风险预警</h3>
                {!selectedCustomer ? (
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-medium text-slate-500 dark:bg-slate-800">待生成</span>
                ) : (
                  <span className="rounded-full bg-red-50 px-2 py-1 text-[10px] font-medium text-red-600">中风险</span>
                )}
              </div>

              {!selectedCustomer ? (
                <div className="flex flex-1 flex-col items-center justify-center text-center">
                  <div className="mb-4 flex space-x-1">
                    <div className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                    <div className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                    <div className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                  </div>
                  <div className="mb-2 text-sm font-bold text-slate-700 dark:text-slate-300">选择确定客户后自动生成</div>
                  <div className="text-xs text-slate-400">当前卡片保持空白提示态，引导你先从顶部选择权限范围内的客户。</div>
                </div>
              ) : (
                <>
                  <ul className="mb-6 space-y-3">
                    <li className="flex items-start space-x-2 text-xs text-slate-600 dark:text-slate-400">
                      <div className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-orange-500" />
                      <span className="leading-relaxed">最近30天沟通频次下降，活跃度较上月回落</span>
                    </li>
                    <li className="flex items-start space-x-2 text-xs text-slate-600 dark:text-slate-400">
                      <div className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-orange-500" />
                      <span className="leading-relaxed">当前方案进入平稳期，客户价值感可能减弱</span>
                    </li>
                    <li className="flex items-start space-x-2 text-xs text-slate-600 dark:text-slate-400">
                      <div className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-orange-500" />
                      <span className="leading-relaxed">高价值VIP客户需尽快形成下一轮经营动作</span>
                    </li>
                  </ul>
                  <div className="mt-auto rounded-xl border border-red-100 bg-red-50/50 p-3 dark:border-red-900/30 dark:bg-red-900/20">
                    <p className="text-xs text-red-600 dark:text-red-400">
                      <span className="font-bold">AI建议：</span>72小时内完成一次主动回访
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
