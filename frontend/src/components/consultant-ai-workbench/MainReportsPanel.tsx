import { AnimatePresence, motion } from 'motion/react';
import { useState, useEffect } from 'react';
import { ArrowRight, BarChart3, Brain, CheckCircle2, Clock, Heart, Sparkles, Users, Zap, Activity } from 'lucide-react';
import type { Spec } from '@json-render/react';
import type { HistoryItem, WorkbenchViewMode } from './types';
import type { SuggestionItem } from './data';
import { AssistantRenderer } from './json-render/registry';
import { apiClient } from '../../services/api';

interface MainReportsPanelProps {
  viewMode: WorkbenchViewMode;
  showNewPlan: boolean;
  historyItems: HistoryItem[];
  suggestionItems: SuggestionItem[];
  /** AI 回复中解析出的 Spec，viewMode=AI_PANEL 时展示 */
  aiSpec?: Spec | null;
}

export function MainReportsPanel({ viewMode, showNewPlan, historyItems, suggestionItems, aiSpec }: MainReportsPanelProps) {
  const [renderState, setRenderState] = useState<Record<string, unknown>>({});

  useEffect(() => {
    if (aiSpec?.state && typeof aiSpec.state === 'object') {
      setRenderState(aiSpec.state as Record<string, unknown>);
    } else {
      setRenderState({});
    }
  }, [aiSpec]);

  /** 处理 AssistantRenderer 的自定义动作，逻辑与 AssistantMessageContent 保持一致 */
  const handleAction = async (actionName: string, params?: Record<string, unknown>) => {
    switch (actionName) {
      case 'remoteQuery': {
        // 当用户点击"查看详情"时，更新 renderState 展示卡片
        if (params?.action && (params.action as any).params?.api_id === 'customer_detail') {
           setRenderState(prev => ({ ...prev, showDetail: true }));
        }
        break;
      }
      case 'saveToServer': {
        const goal = typeof params?.goal === 'string' ? params.goal : '';
        try {
          await apiClient.post('/api/v1/consultant/plan/save', { goal });
          console.info('[MainReportsPanel] 规划已保存:', goal);
        } catch (err) {
          console.error('[MainReportsPanel] saveToServer 失败:', err);
        }
        break;
      }
      default:
        console.warn(`[MainReportsPanel] 未处理的 action: ${actionName}`, params);
    }
  };

  return (
    <div className="col-span-6 flex flex-col space-y-6 overflow-y-auto pr-2 custom-scrollbar">
      <AnimatePresence mode="wait">
        {/* AI_PANEL：AI 对话回复中存在 Spec 时，将交互卡片渲染到中央主面板 */}
        {viewMode === 'AI_PANEL' && aiSpec && (
          <motion.div
            key="ai_panel"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            transition={{ duration: 0.25 }}
            className="space-y-4"
          >
            {/* 顶部标题栏 */}
            <div className="flex items-center space-x-2 px-1">
              <Sparkles className="w-4 h-4 text-brand" />
              <span className="text-xs font-bold text-brand">AI 结构化规划卡片</span>
              <span className="text-xs text-slate-400">· 来自最新对话回复</span>
            </div>

            {/* AssistantRenderer：Standalone Mode，直接渲染 Spec 卡片 */}
            <AssistantRenderer
              spec={aiSpec}
              state={renderState}
              onAction={handleAction}
            />
          </motion.div>
        )}

        {viewMode === 'FULL_INFO' && (
          <motion.div
            key="full_info"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="space-y-6"
          >

            <div className="bg-white/60 backdrop-blur-xl rounded-3xl border border-white/80 shadow-sm p-6">
              <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center">
                <Users className="w-5 h-5 mr-2 text-brand" />
                客户全量资产档案 - 张三
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
                  <div className="text-[10px] text-slate-400 font-bold uppercase mb-2">基础与健康</div>
                  <ul className="space-y-2 text-xs text-slate-600">
                    <li className="flex justify-between"><span>健康状况:</span> <span className="font-bold text-slate-900">气虚体质 / 慢性疲劳</span></li>
                    <li className="flex justify-between"><span>过敏史:</span> <span className="font-bold text-slate-900">无</span></li>
                    <li className="flex justify-between"><span>重点关注:</span> <span className="font-bold text-brand">心血管健康</span></li>
                  </ul>
                </div>
                <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
                  <div className="text-[10px] text-slate-400 font-bold uppercase mb-2">已购方案</div>
                  <ul className="space-y-2 text-xs text-slate-600">
                    <li className="flex justify-between"><span>体检方案:</span> <span className="font-bold text-slate-900">尊享年度体检 B</span></li>
                    <li className="flex justify-between"><span>治疗方案:</span> <span className="font-bold text-slate-900">中医调理 (剩余4次)</span></li>
                    <li className="flex justify-between"><span>大会门票:</span> <span className="font-bold text-purple-600">2026 康养峰会 (VIP)</span></li>
                  </ul>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {viewMode === 'HISTORY' && (
          <motion.div
            key="history"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="bg-white rounded-3xl border border-slate-100 shadow-sm p-6"
          >
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center">
              <Clock className="w-5 h-5 mr-2 text-brand" />
              近半年治疗记录 (12次)
            </h3>
            <div className="space-y-3">
              {historyItems.map((item) => (
                <div key={item.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-3xl border border-slate-100">
                  <div className="flex items-center space-x-4">
                    <div className="text-xs font-bold text-slate-400">{item.date}</div>
                    <div className="text-sm font-bold text-slate-700">{item.type}</div>
                  </div>
                  <div className="flex items-center space-x-4">
                    <span className="text-xs text-slate-500">{item.detail}</span>
                    <span className={item.result === '显著' ? 'px-2 py-0.5 rounded text-[10px] font-bold bg-green-100 text-green-600' : 'px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-600'}>
                      {item.result}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {viewMode === 'COMPARISON' && (
          <motion.div
            key="comparison"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="bg-white rounded-3xl border border-slate-100 shadow-sm p-6"
          >
            <h3 className="text-lg font-bold text-slate-900 mb-6 flex items-center">
              <BarChart3 className="w-5 h-5 mr-2 text-brand" />
              治疗结果对比分析
            </h3>
            <div className="grid grid-cols-2 gap-8">
              <div className="space-y-4">
                <div className="text-xs font-bold text-slate-500 text-center">气虚指数 (越低越好)</div>
                <div className="h-32 flex items-end justify-around px-4">
                  <div className="w-8 bg-slate-200 rounded-t-lg h-[80%] relative group">
                    <span className="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] font-bold">8.5</span>
                    <span className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-[10px] text-slate-400">半年前</span>
                  </div>
                  <div className="w-8 bg-brand rounded-t-lg h-[45%] relative group">
                    <span className="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] font-bold text-brand">4.2</span>
                    <span className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-[10px] text-slate-400">现在</span>
                  </div>
                </div>
              </div>
              <div className="space-y-4">
                <div className="text-xs font-bold text-slate-500 text-center">皮肤紧致度 (越高越好)</div>
                <div className="h-32 flex items-end justify-around px-4">
                  <div className="w-8 bg-slate-200 rounded-t-lg h-[60%] relative group">
                    <span className="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] font-bold">65%</span>
                    <span className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-[10px] text-slate-400">半年前</span>
                  </div>
                  <div className="w-8 bg-purple-500 rounded-t-lg h-[85%] relative group">
                    <span className="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] font-bold text-purple-500">80%</span>
                    <span className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-[10px] text-slate-400">现在</span>
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-12 p-4 bg-green-50/80 backdrop-blur-xl rounded-3xl border border-green-100 flex items-start space-x-3 shadow-sm">
              <CheckCircle2 className="w-5 h-5 text-green-500 mt-0.5" />
              <p className="text-xs text-green-800 leading-relaxed">
                <span className="font-bold">AI 结论：</span>对比半年前，客户气虚症状得到显著改善（下降 50.5%），皮肤紧致度提升 15%。当前方案非常有效，建议继续保持。
              </p>
            </div>
          </motion.div>
        )}

        {viewMode === 'SUGGESTIONS' && (
          <motion.div
            key="suggestions"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="bg-white rounded-3xl border border-slate-100 shadow-sm p-6"
          >
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center">
              <Heart className="w-5 h-5 mr-2 text-brand" />
              健康追踪建议
            </h3>
            <div className="grid grid-cols-1 gap-4">
              {suggestionItems.map((item) => (
                <div key={item.id} className="p-4 bg-slate-50 rounded-3xl border border-slate-100 flex items-start space-x-3">
                  <div className="p-2 bg-white rounded-xl shadow-sm text-brand"><item.icon className="w-4 h-4" /></div>
                  <div>
                    <div className="text-sm font-bold text-slate-900">{item.title}</div>
                    <div className="text-xs text-slate-500 mt-1">{item.content}</div>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {viewMode === 'PLAN' && (
          <motion.div key="plan_view" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-6">
            <AnimatePresence>
              {showNewPlan && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, y: 20 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  className="bg-gradient-to-br from-brand to-brand-hover rounded-3xl p-1 shadow-xl shadow-brand/20"
                >
                  <div className="bg-white/60 backdrop-blur-xl rounded-3xl p-6 shadow-sm border border-white/80">
                    <div className="flex items-center justify-between mb-6">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 bg-brand/10 rounded-xl flex items-center justify-center text-brand">
                          <Sparkles className="w-6 h-6" />
                        </div>
                        <div>
                          <h3 className="text-lg font-bold text-slate-900">AI 1+X 智能规划方案 (张三)</h3>
                          <p className="text-xs text-slate-400 font-medium">基于全量数据分析生成的个性化路径</p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="px-3 py-1 bg-green-50 text-green-600 rounded-full text-[10px] font-bold border border-green-100">高匹配度 98%</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 mb-6">
                      <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
                        <div className="flex items-center space-x-2 mb-3">
                          <div className="w-6 h-6 bg-brand text-white rounded-full flex items-center justify-center text-[10px] font-bold">1</div>
                          <span className="text-sm font-bold text-slate-900">核心基础项</span>
                        </div>
                        <div className="text-lg font-bold text-slate-900 mb-1">年度健康管理续费</div>
                        <div className="text-xs text-slate-500">¥28,000 · 12个月</div>
                      </div>
                      <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
                        <div className="flex items-center space-x-2 mb-3">
                          <div className="w-6 h-6 bg-purple-500 text-white rounded-full flex items-center justify-center text-[10px] font-bold">X</div>
                          <span className="text-sm font-bold text-slate-900">增值推荐项</span>
                        </div>
                        <div className="text-lg font-bold text-slate-900 mb-1">中医调理 + 抗衰组合</div>
                        <div className="text-xs text-slate-500">¥40,000 · 6个月</div>
                      </div>
                    </div>

                    <div className="space-y-3 mb-6">
                      <div className="flex items-center justify-between p-3 bg-brand/5 rounded-3xl border border-brand/10">
                        <div className="flex items-center space-x-3">
                          <Brain className="w-4 h-4 text-brand" />
                          <span className="text-xs font-bold text-slate-700">AI 核心策略：挽留 + 深度消耗</span>
                        </div>
                        <ArrowRight className="w-4 h-4 text-brand" />
                      </div>
                      <p className="text-xs text-slate-500 leading-relaxed px-1">
                        针对张三 75 分的流失风险，方案优先通过中医调理（客户高偏好）建立高频触达，配合年度续费锁定长期服务价值。
                      </p>
                    </div>

                    <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                      <div className="flex items-center space-x-6">
                        <div>
                          <div className="text-[10px] text-slate-400 font-bold uppercase">总计金额</div>
                          <div className="text-xl font-bold text-slate-900">¥68,000</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-slate-400 font-bold uppercase">预估ROI</div>
                          <div className="text-xl font-bold text-green-500">+240%</div>
                        </div>
                      </div>
                      <button type="button" className="px-6 py-2.5 bg-brand text-white rounded-xl text-sm font-bold shadow-lg shadow-brand/20 hover:bg-brand-hover transition-all">
                        应用此方案
                      </button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div className="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden">
              <div className="p-5 border-b border-slate-50 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 bg-brand rounded-full flex items-center justify-center text-white font-bold text-sm">1</div>
                  <h3 className="font-bold text-slate-900">基础项 · 年度健康管理套餐续费</h3>
                </div>
                <span className="px-3 py-1 bg-brand/10 text-brand text-[10px] rounded-full font-bold">核心推荐</span>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-3 gap-6 mb-6">
                  <div className="bg-slate-50 rounded-2xl p-5 border border-slate-100">
                    <div className="text-[10px] text-slate-400 mb-1">套餐金额</div>
                    <div className="text-2xl font-bold text-slate-900 tracking-tight">¥28,000</div>
                  </div>
                  <div className="bg-slate-50 rounded-2xl p-5 border border-slate-100">
                    <div className="text-[10px] text-slate-400 mb-1">消耗周期</div>
                    <div className="text-2xl font-bold text-slate-900 tracking-tight">12 <span className="text-sm font-normal text-slate-500">个月</span></div>
                  </div>
                  <div className="bg-slate-50 rounded-2xl p-5 border border-slate-100">
                    <div className="text-[10px] text-slate-400 mb-1">AI匹配度</div>
                    <div className="text-2xl font-bold text-brand tracking-tight">95%</div>
                  </div>
                </div>
                <div className="p-4 bg-amber-50/50 rounded-2xl border border-amber-100 flex items-start space-x-3">
                  <Brain className="w-5 h-5 text-amber-500 mt-0.5" />
                  <p className="text-xs text-amber-800 leading-relaxed">
                    <span className="font-bold">AI推荐理由：</span>张三为VIP客户，入会3年，年度套餐可保持客户粘性并覆盖基础健康管理需求，续约率历史数据显示同类客户达88%。
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden">
              <div className="p-5 border-b border-slate-50 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 bg-purple-500 rounded-full flex items-center justify-center text-white font-bold text-sm">X</div>
                  <h3 className="font-bold text-slate-900">增值项 · AI个性化推荐组合</h3>
                </div>
                <div className="flex items-center text-brand text-[10px] font-bold">
                  <Sparkles className="w-3.5 h-3.5 mr-1" />
                  AI生成
                </div>
              </div>
              <div className="p-6 space-y-4">
                <button type="button" className="flex w-full items-center justify-between p-5 rounded-2xl bg-slate-50 border border-slate-100 hover:border-brand/30 transition-all group text-left">
                  <div className="flex items-center space-x-4">
                    <div className="p-3 bg-white rounded-xl shadow-sm">
                      <Activity className="w-6 h-6 text-brand" />
                    </div>
                    <div>
                      <div className="text-sm font-bold text-slate-900">中医体质调理 × 6次</div>
                      <div className="text-[10px] text-slate-400 mt-0.5">针对气虚体质，改善亚健康状态</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-slate-900">¥18,000</div>
                    <div className="text-[10px] text-brand font-bold mt-0.5">匹配度 92%</div>
                  </div>
                </button>
                <button type="button" className="flex w-full items-center justify-between p-5 rounded-2xl bg-slate-50 border border-slate-100 hover:border-brand/30 transition-all group text-left">
                  <div className="flex items-center space-x-4">
                    <div className="p-3 bg-white rounded-xl shadow-sm">
                      <Zap className="w-6 h-6 text-purple-500" />
                    </div>
                    <div>
                      <div className="text-sm font-bold text-slate-900">光电抗衰疗程 × 3次</div>
                      <div className="text-[10px] text-slate-400 mt-0.5">紧致提升，延缓衰老，适合65岁以上客户</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-slate-900">¥22,000</div>
                    <div className="text-[10px] text-brand font-bold mt-0.5">匹配度 87%</div>
                  </div>
                </button>
                <div className="p-4 bg-blue-50/50 rounded-2xl border border-blue-100 flex items-start space-x-3">
                  <Brain className="w-5 h-5 text-blue-500 mt-0.5" />
                  <p className="text-xs text-blue-800 leading-relaxed">
                    <span className="font-bold">AI洞察：</span>基于张三体检报告（气虚体质）和同画像客户消费偏好分析，中医调理+光电抗衰组合的接受率为78%，预计6个月内可消耗完毕。
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white/60 backdrop-blur-xl rounded-3xl border border-white/80 shadow-lg p-6 flex items-center justify-between">
              <div className="flex items-center space-x-12">
                <div>
                  <div className="text-[10px] text-slate-400 mb-1 uppercase tracking-wider">方案总计</div>
                  <div className="text-3xl font-bold text-slate-900 tracking-tight">¥68,000</div>
                </div>
                <div className="h-10 w-px bg-slate-100"></div>
                <div>
                  <div className="text-[10px] text-slate-400 mb-1 uppercase tracking-wider">消耗周期</div>
                  <div className="text-xl font-bold text-slate-900 tracking-tight">6 <span className="text-sm font-normal text-slate-500">个月</span></div>
                </div>
                <div className="h-10 w-px bg-slate-100"></div>
                <div>
                  <div className="text-[10px] text-slate-400 mb-1 uppercase tracking-wider">AI预测ROI</div>
                  <div className="text-xl font-bold text-green-500 tracking-tight">+240%</div>
                </div>
              </div>
              <button className="px-8 py-4 bg-brand text-white rounded-2xl font-bold shadow-xl shadow-brand/20 hover:bg-brand-hover transition-all transform hover:-translate-y-0.5 active:translate-y-0" type="button">
                <CheckCircle2 className="w-5 h-5 mr-2" />
                确认方案
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
