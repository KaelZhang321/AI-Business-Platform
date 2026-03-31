// 顾问 AI 工作台：聚合客户信息、AI 规划建议和顾问操作入口。
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Users, 
  Search, 
  Filter, 
  TrendingUp, 
  Brain, 
  MessageSquare, 
  ChevronRight,
  Calendar,
  Clock,
  Target,
  FileText,
  Star,
  ArrowUpRight,
  Sparkles,
  Send,
  Bell,
  Download,
  RefreshCw,
  Mic,
  AlertTriangle,
  Zap,
  Activity,
  CheckCircle2,
  PlusCircle,
  ArrowRight,
  BarChart3,
  Heart,
  Stethoscope,
  Ticket,
  Utensils,
  Moon
} from 'lucide-react';

type PlanningMessageRole = 'ai' | 'user';

interface PlanningMessage {
  id: string;
  role: PlanningMessageRole;
  content: string;
}

let planningMessageCounter = 0;

function createPlanningMessage(role: PlanningMessageRole, content: string): PlanningMessage {
  planningMessageCounter += 1;
  return {
    id: `planning-message-${planningMessageCounter}`,
    role,
    content,
  };
}

export function ConsultantAIWorkbench() {
  const [planningChatMessage, setPlanningChatMessage] = useState('');
  const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);
  const [showNewPlan, setShowNewPlan] = useState(false);
  const [aiName, setAiName] = useState('小智');
  const [isNaming, setIsNaming] = useState(false);
  const [viewMode, setViewMode] = useState<'PLAN' | 'HISTORY' | 'COMPARISON' | 'SUGGESTIONS' | 'FULL_INFO'>('PLAN');
  const historyItems = [
    { id: 'history-1', date: '2026-03-10', type: '中医调理', result: '良好', detail: '气虚症状有所缓解' },
    { id: 'history-2', date: '2026-02-15', type: '光电抗衰', result: '显著', detail: '面部紧致度提升' },
    { id: 'history-3', date: '2026-01-20', type: '中医调理', result: '一般', detail: '睡眠质量待改善' },
    { id: 'history-4', date: '2025-12-05', type: '年度体检', result: '完成', detail: '各项指标基本稳定' },
  ] as const;
  const suggestionItems = [
    { id: 'diet', title: '饮食建议', content: '增加山药、大枣等补气食物，避免生冷。', icon: Utensils },
    { id: 'exercise', title: '运动建议', content: '每日进行 30 分钟八段锦或太极拳，不宜剧烈运动。', icon: Activity },
    { id: 'sleep', title: '作息建议', content: '晚间 10:30 前入睡，保证 7-8 小时高质量睡眠。', icon: Moon },
  ] as const;
  
  const [planningMessages, setPlanningMessages] = useState<PlanningMessage[]>([
    createPlanningMessage(
      'ai',
      `您好！我是您的 AI 助手 ${aiName}。作为您的健康管家助手，我可以帮您整理客户的全量信息、查询治疗记录、对比治疗结果并生成追踪建议。您可以试着对我说：“整理张三的所有信息”或“对比张三近半年的治疗结果”。`,
    ),
  ]);

  const handleSendPlanningMessage = (text?: string) => {
    const input = text || planningChatMessage;
    if (!input.trim()) return;
    
    setPlanningMessages((prev) => [...prev, createPlanningMessage('user', input)]);
    setPlanningChatMessage('');

    setIsGeneratingPlan(true);
    
    // Simulate AI processing different intents
    setTimeout(() => {
      let response = '';
      if (input.includes('整理') || input.includes('信息')) {
        response = `✨ 已为您整理好客户【张三】的全量信息。包含基础画像、健康状况、已购体检方案及大会门票信息。详情已在右侧看板展示。`;
        setViewMode('FULL_INFO');
      } else if (input.includes('记录') || input.includes('半年')) {
        response = `✨ 已调取【张三】近半年的治疗记录。共计 12 次治疗，包含中医调理与光电项目。`;
        setViewMode('HISTORY');
      } else if (input.includes('对比') || input.includes('结果')) {
        response = `✨ 治疗结果对比分析已完成。数据显示：气虚体质改善明显，皮肤紧致度提升 15%。`;
        setViewMode('COMPARISON');
      } else if (input.includes('建议') || input.includes('追踪')) {
        response = `✨ 已根据最新治疗结果生成健康追踪建议。建议加强居家饮食调理，并按期进行下月复查。`;
        setViewMode('SUGGESTIONS');
      } else if (input.includes('1+x') || input.includes('规划')) {
        response = `✨ 1+X 智能规划方案已生成。已为您匹配最优消耗路径。`;
        setViewMode('PLAN');
        setShowNewPlan(true);
      } else {
        response = `正在为您处理指令...`;
      }

      setPlanningMessages((prev) => [...prev, createPlanningMessage('ai', response)]);
      setIsGeneratingPlan(false);
    }, 1500);
  };

  return (
    <div className="h-full flex flex-col space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">我的 AI 工作台</h2>
          <p className="text-sm text-slate-500">健康管家专属智能助手，全方位管理客户健康资产</p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input 
              type="text" 
              placeholder="搜索客户姓名/ID..." 
              className="pl-9 pr-4 py-2 bg-white border border-slate-200 rounded-3xl text-sm focus:ring-2 focus:ring-brand outline-none w-64"
            />
          </div>
          <button className="p-2 bg-white border border-slate-200 rounded-3xl hover:bg-slate-50">
            <Filter className="w-4 h-4 text-slate-600" />
          </button>
        </div>
      </div>

      {/* Customer Info Bar */}
      <div className="p-4 bg-white/60 backdrop-blur-xl rounded-3xl border border-white/80 flex items-center justify-between shadow-sm">
        <div className="flex items-center space-x-4">
          <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center text-purple-600 font-bold text-lg">张</div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-lg font-bold text-slate-900">张三 · VIP会员</span>
              <span className="px-2 py-0.5 bg-purple-50 text-purple-600 text-[10px] rounded font-bold uppercase tracking-wider">VVIP</span>
            </div>
            <div className="text-xs text-slate-500 mt-0.5">65岁 · 退休干部 · 入会3年 · 剩余项目金 ¥58,800</div>
          </div>
        </div>
        <div className="flex items-center space-x-8">
          <div className="flex items-center space-x-4">
            <div className="flex items-center px-3 py-1.5 bg-purple-50 text-purple-600 rounded-full text-xs font-bold">
              <Brain className="w-3.5 h-3.5 mr-1.5" />
              AI已分析
            </div>
            <div className="flex items-center px-3 py-1.5 bg-red-50 text-red-600 rounded-full text-xs font-bold">
              <Activity className="w-3.5 h-3.5 mr-1.5" />
              流失风险 75分
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <button type="button" className="flex items-center px-4 py-2 bg-white border border-slate-200 rounded-3xl text-xs font-bold text-slate-600 hover:bg-slate-50 transition-all">
              <Download className="w-4 h-4 mr-2" />
              导出PDF
            </button>
            <button type="button" className="flex items-center px-4 py-2 bg-brand text-white rounded-3xl text-xs font-bold shadow-lg shadow-brand/20 hover:bg-brand-hover transition-all">
              <RefreshCw className="w-4 h-4 mr-2" />
              AI重新生成
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="flex-1 grid grid-cols-12 gap-6 overflow-hidden">
        
        {/* Left Sidebar: AI Assistant */}
        <div className="col-span-3 flex flex-col bg-white/60 backdrop-blur-xl rounded-3xl border border-white/80 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-50 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-5 h-5 text-brand" />
              {isNaming ? (
                <input 
                  autoFocus
                  className="bg-transparent border-b border-brand outline-none font-bold text-slate-900 w-24"
                  value={aiName}
                  onChange={(e) => setAiName(e.target.value)}
                  onBlur={() => setIsNaming(false)}
                  onKeyDown={(e) => e.key === 'Enter' && setIsNaming(false)}
                />
              ) : (
                <button
                  type="button"
                  className="font-bold text-slate-900 hover:text-brand transition-colors"
                  onClick={() => setIsNaming(true)}
                  title="点击重命名助手"
                >
                  {aiName}
                </button>
              )}
              <span className="text-[10px] bg-brand/10 text-brand px-1.5 py-0.5 rounded font-bold">AI 助手</span>
            </div>
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          </div>
          
          <div className="flex-1 overflow-y-auto p-5 space-y-6 custom-scrollbar">
            <div className="p-4 bg-gradient-to-br from-brand/5 to-purple-50 rounded-3xl border border-brand/10 mb-2">
              <p className="text-[10px] text-slate-500 leading-relaxed">
                我是您的数字健康管家 <span className="font-bold text-brand">{aiName}</span>。我已加载您负责的 128 位客户数据，随时待命。
              </p>
            </div>
            <AnimatePresence initial={false}>
              {planningMessages.map((msg) => (
                <motion.div 
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                >
                  {msg.role === 'ai' && (
                    <div className="flex items-center space-x-2 mb-2">
                      <div className="w-6 h-6 bg-brand rounded-lg flex items-center justify-center text-white text-[10px] font-bold">AI</div>
                      <span className="text-[10px] font-bold text-slate-400">{aiName} 助手</span>
                    </div>
                  )}
                  <div className={`max-w-[95%] p-4 rounded-3xl text-sm leading-relaxed ${
                    msg.role === 'user' 
                      ? 'bg-brand text-white rounded-tr-none' 
                      : 'bg-slate-50 text-slate-700 rounded-tl-none border border-slate-100'
                  }`}>
                    {msg.content.split('\n').map((line, index) => (
                      <p key={`${msg.id}-${index}`} className={index > 0 ? 'mt-2' : ''}>{line}</p>
                    ))}
                  </div>
                </motion.div>
              ))}
              {isGeneratingPlan && (
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center space-x-3 p-4 bg-brand/5 rounded-2xl border border-brand/10"
                >
                  <RefreshCw className="w-4 h-4 text-brand animate-spin" />
                  <span className="text-xs font-bold text-brand">AI 正在分析全量数据并生成规划...</span>
                </motion.div>
              )}
            </AnimatePresence>
            
            <button 
              onClick={() => handleSendPlanningMessage('整理张三的所有信息')}
              className="w-full py-3 bg-slate-50 text-slate-600 text-xs font-bold rounded-3xl border border-slate-100 hover:bg-brand/5 hover:text-brand hover:border-brand/20 transition-all text-left px-4 flex items-center justify-between group"
            >
              <span>整理张三的所有信息</span>
              <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-all" />
            </button>
            <button 
              onClick={() => handleSendPlanningMessage('查看张三近半年治疗记录')}
              className="w-full py-3 bg-slate-50 text-slate-600 text-xs font-bold rounded-3xl border border-slate-100 hover:bg-brand/5 hover:text-brand hover:border-brand/20 transition-all text-left px-4 flex items-center justify-between group"
            >
              <span>查看张三近半年治疗记录</span>
              <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-all" />
            </button>
            <button 
              onClick={() => handleSendPlanningMessage('对比张三治疗结果')}
              className="w-full py-3 bg-slate-50 text-slate-600 text-xs font-bold rounded-3xl border border-slate-100 hover:bg-brand/5 hover:text-brand hover:border-brand/20 transition-all text-left px-4 flex items-center justify-between group"
            >
              <span>对比张三治疗结果</span>
              <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-all" />
            </button>
            <button 
              onClick={() => handleSendPlanningMessage('生成健康追踪建议')}
              className="w-full py-3 bg-slate-50 text-slate-600 text-xs font-bold rounded-3xl border border-slate-100 hover:bg-brand/5 hover:text-brand hover:border-brand/20 transition-all text-left px-4 flex items-center justify-between group"
            >
              <span>生成健康追踪建议</span>
              <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-all" />
            </button>
          </div>

          <div className="p-4 bg-white border-t border-slate-100">
            <div className="relative flex items-center">
              <input 
                type="text" 
                value={planningChatMessage}
                onChange={(e) => setPlanningChatMessage(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendPlanningMessage()}
                placeholder={`给${aiName}下达指令...`}
                className="w-full pl-4 pr-12 py-3 bg-slate-50 border border-slate-100 rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-brand/20 focus:border-brand transition-all"
              />
              <button
                type="button"
                onClick={handleSendPlanningMessage}
                aria-label="发送规划指令"
                className="absolute right-2 p-2 bg-brand text-white rounded-xl hover:bg-brand-dark transition-colors shadow-sm shadow-brand/20"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Middle Column: Dynamic AI Reports */}
        <div className="col-span-6 flex flex-col space-y-6 overflow-y-auto pr-2 custom-scrollbar">
          <AnimatePresence mode="wait">
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
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${item.result === '显著' ? 'bg-green-100 text-green-600' : 'bg-blue-100 text-blue-600'}`}>
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
              <motion.div
                key="plan_view"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-6"
              >
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

                {/* Section 1: Basic Item */}
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

                {/* Section 2: Value-added Item */}
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

                {/* Footer Summary */}
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
                  <button className="px-8 py-4 bg-brand text-white rounded-2xl font-bold shadow-xl shadow-brand/20 hover:bg-brand-hover transition-all transform hover:-translate-y-0.5 active:translate-y-0">
                    <CheckCircle2 className="w-5 h-5 mr-2" />
                    确认方案
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Right Sidebar: Insights */}
        <div className="col-span-3 space-y-6 overflow-y-auto pr-2 custom-scrollbar">
          {/* AI Consumption Prediction */}
          <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-bold text-slate-900 flex items-center">
                <TrendingUp className="w-5 h-5 mr-2 text-brand" />
                AI 消耗预测
              </h3>
              <span className="text-[10px] text-green-500 font-bold bg-green-50 px-2 py-0.5 rounded">6个月预测</span>
            </div>
            <div className="space-y-6 relative before:absolute before:left-[7px] before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-100">
              <div className="relative pl-6">
                <div className="absolute left-0 top-1.5 w-3.5 h-3.5 bg-brand rounded-full border-2 border-white shadow-sm"></div>
                <div className="text-sm font-bold text-slate-800">4月 — 启动期</div>
                <div className="text-[10px] text-slate-500 mt-1">体检评估 + 首次中医调理</div>
                <div className="text-[10px] text-brand font-bold mt-1">预计消耗 ¥8,500</div>
              </div>
              <div className="relative pl-6">
                <div className="absolute left-0 top-1.5 w-3.5 h-3.5 bg-purple-500 rounded-full border-2 border-white shadow-sm"></div>
                <div className="text-sm font-bold text-slate-800">5-6月 — 密集期</div>
                <div className="text-[10px] text-slate-500 mt-1">中医调理4次 + 光电抗衰2次</div>
                <div className="text-[10px] text-brand font-bold mt-1">预计消耗 ¥32,000</div>
              </div>
              <div className="relative pl-6 opacity-60">
                <div className="absolute left-0 top-1.5 w-3.5 h-3.5 bg-green-500 rounded-full border-2 border-white shadow-sm"></div>
                <div className="text-sm font-bold text-slate-800">7-9月 — 巩固期</div>
                <div className="text-[10px] text-slate-500 mt-1">最后中医调理1次 + 抗衰1次 + 复查</div>
                <div className="text-[10px] text-brand font-bold mt-1">预计消耗 ¥27,500</div>
              </div>
            </div>
          </div>

          {/* AI Upsell Potential */}
          <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-6">
            <h3 className="font-bold text-slate-900 flex items-center mb-6">
              <Zap className="w-5 h-5 mr-2 text-brand" />
              AI 升单潜力
            </h3>
            <div className="grid grid-cols-3 gap-3 mb-6">
              <div className="bg-purple-50 rounded-3xl p-3 text-center border border-purple-100">
                <div className="text-lg font-bold text-purple-600">高</div>
                <div className="text-[8px] text-purple-400 font-bold uppercase">升单潜力</div>
              </div>
              <div className="bg-blue-50 rounded-3xl p-3 text-center border border-blue-100">
                <div className="text-lg font-bold text-blue-600">45%</div>
                <div className="text-[8px] text-blue-400 font-bold uppercase">转化概率</div>
              </div>
              <div className="bg-green-50 rounded-3xl p-3 text-center border border-green-100">
                <div className="text-lg font-bold text-green-600">¥80K</div>
                <div className="text-[8px] text-green-400 font-bold uppercase">预估金额</div>
              </div>
            </div>
            <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs font-bold text-slate-700">推荐：中医调理金卡</div>
                <button type="button" className="px-3 py-1 bg-brand text-white text-[10px] font-bold rounded-lg hover:bg-brand-hover transition-all">生成话术</button>
              </div>
              <p className="text-[10px] text-slate-500 leading-relaxed">AI匹配度 92% · 基于通话意向分析</p>
            </div>
          </div>

          {/* AI Risk Warning */}
          <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-bold text-slate-900 flex items-center">
                <AlertTriangle className="w-5 h-5 mr-2 text-red-500" />
                AI 风险预警
              </h3>
              <span className="text-[10px] text-red-500 font-bold bg-red-50 px-2 py-0.5 rounded">高风险</span>
            </div>
            <ul className="space-y-3 mb-6">
              <li className="flex items-start space-x-2 text-[10px] text-slate-600">
                <div className="w-1.5 h-1.5 rounded-full bg-red-500 mt-1 flex-shrink-0"></div>
                <span>消耗停滞 30天，流失风险评分 75</span>
              </li>
              <li className="flex items-start space-x-2 text-[10px] text-slate-600">
                <div className="w-1.5 h-1.5 rounded-full bg-orange-500 mt-1 flex-shrink-0"></div>
                <span>上次治疗满意度偏低（沟通记录分析）</span>
              </li>
              <li className="flex items-start space-x-2 text-[10px] text-slate-600">
                <div className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1 flex-shrink-0"></div>
                <span>同期VIP客户活跃度正常，张三异常</span>
              </li>
            </ul>
            <div className="p-4 bg-red-50/50 rounded-2xl border border-red-100 flex items-start space-x-3">
              <MessageSquare className="w-5 h-5 text-red-500 mt-0.5" />
              <p className="text-xs text-red-800 leading-relaxed">
                <span className="font-bold">AI建议：</span>立即主动回访，使用关怀型话术挽留
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
