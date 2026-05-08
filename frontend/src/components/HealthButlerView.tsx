// 健康管家视图：展示客户健康数据、随访任务和 AI 提醒内容。
import React, { useState } from 'react';
import { 
  Sparkles, MessageSquare, FileText, CheckSquare, 
  TrendingUp, Users, Calendar, AlertCircle, 
  ChevronRight, Send, Upload, Search, Bell,
  Activity, Heart, Thermometer, Clock, User, ArrowLeft, RefreshCw
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

/** 模拟健康管家客户列表数据 */
const MOCK_CUSTOMERS = [
  { id: 1, name: '张晓彤', status: '高血压术后7天', tags: ['随访 D3', '情绪监测', '解读完成', '用药核对'], avatar: '张', theme: '术后修复', consumption: 38, bp: '132/86', lastBp: '138/92', lipid: '3.1 (↑)', weight: '58kg', risk: '情绪0.72', lastVisit: '2026-03-13' },
  { id: 2, name: '李娜', status: '糖尿病常规管理', tags: ['血糖监测', '饮食指导', '运动打卡'], avatar: '李', theme: '慢病管理', consumption: 65, bp: '120/80', lastBp: '122/82', lipid: '2.8', weight: '62kg', risk: '低风险', lastVisit: '2026-03-15' },
  { id: 3, name: '王曼曼', status: '产后康复第14天', tags: ['盆底肌训练', '母乳指导', '心理疏导'], avatar: '王', theme: '产后修复', consumption: 20, bp: '115/75', lastBp: '118/78', lipid: '2.5', weight: '55kg', risk: '轻度焦虑', lastVisit: '2026-03-10' },
  { id: 4, name: '赵心语', status: '减重管理第30天', tags: ['体脂监测', '高强度训练', '代餐计划'], avatar: '赵', theme: '体态管理', consumption: 85, bp: '110/70', lastBp: '112/72', lipid: '2.1', weight: '52kg', risk: '低风险', lastVisit: '2026-03-18' },
];

/** 健康管家助手气泡消息类型联合体 */
type ButlerMessage =
  | {
      id: string;
      role: 'ai' | 'user';
      content: string;
      type?: never;
      customer?: never;
    }
  | {
      id: string;
      role: 'ai' | 'user';
      content: string;
      type: 'dashboard';
      customer: (typeof MOCK_CUSTOMERS)[number];
    };

/** 健康管家助手气泡消息创建载荷类型 */
type ButlerMessagePayload =
  | {
      role: 'ai' | 'user';
      content: string;
    }
  | {
      role: 'ai' | 'user';
      content: string;
      type: 'dashboard';
      customer: (typeof MOCK_CUSTOMERS)[number];
    };

let butlerMessageCounter = 0;

/** 助手消息工厂函数：分配递增 ID 和通用结构 */
function createButlerMessage(message: ButlerMessagePayload): ButlerMessage {
  butlerMessageCounter += 1;
  return {
    id: `butler-message-${butlerMessageCounter}`,
    ...message,
  };
}

/**
 * 健康管家视图组件：展示客户健康数据、随访任务和 AI 提醒内容。
 * 包含搜索过滤、AI 助手对话窗、客户卡片列表及侧边栏。
 */
export function HealthButlerView() {
  const [selectedCustomer, setSelectedCustomer] = useState<typeof MOCK_CUSTOMERS[0] | null>(null);
  const [chatInput, setChatInput] = useState('');
  const [messages, setMessages] = useState<ButlerMessage[]>([
    createButlerMessage({
      role: 'ai',
      content: '您好！我是您的 AI 健康助手。您可以问我关于客户健康状况、随访计划或 ERP 数据同步的问题。',
    }),
  ]);

  const handleSendMessage = (text?: string) => {
    const input = text || chatInput;
    if (!input.trim()) return;
    
    const newMessages = [...messages, createButlerMessage({ role: 'user', content: input })];
    setMessages(newMessages);
    if (!text) setChatInput('');
    
    // Mock AI response
    setTimeout(() => {
      if (input.includes('张晓彤') && (input.includes('查询') || input.includes('健康状态'))) {
        const customer = MOCK_CUSTOMERS.find(c => c.name === '张晓彤');
        if (customer) {
          setMessages((prev) => [
            ...prev,
            createButlerMessage({
              role: 'ai',
              content: `已为您找到客户 ${customer.name} 的实时健康数据看板。您可以点击下方按钮将其添加至工作台进行深度分析。`,
              type: 'dashboard',
              customer,
            }),
          ]);
        }
      } else {
        setMessages((prev) => [
          ...prev,
          createButlerMessage({
            role: 'ai',
            content: `收到您的指令："${input}"。正在为您分析客户数据并同步最新状态...`,
          }),
        ]);
      }
    }, 1000);
  };

  if (!selectedCustomer) {
    return (
      <div className="h-full flex flex-col space-y-6 animate-in fade-in zoom-in-95 duration-500">
        {/* Top: Search & Filter Bar */}
        <div className="flex items-center justify-between bg-white/60 backdrop-blur-xl p-6 rounded-3xl border border-white/80 shadow-sm">
          <div className="flex items-center space-x-4 flex-1 max-w-xl">
            <div className="relative flex-1 group">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 group-focus-within:text-brand transition-colors" />
              <input 
                type="text" 
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder="搜索客户、询问 AI 或输入指令..." 
                className="w-full bg-slate-50/50 border border-slate-100 rounded-3xl py-3 pl-12 pr-4 text-base focus:outline-none focus:ring-2 focus:ring-brand/10 focus:border-brand/30 transition-all text-slate-900"
              />
            </div>
            <div className="flex bg-slate-50/50 p-1 rounded-3xl border border-slate-100">
              {['全部', '术后修复', '慢病管理', '高风险'].map((tag, i) => (
                <button 
                  key={tag} 
                  className={`px-5 py-2 rounded-3xl text-sm font-bold transition-all ${i === 0 ? 'bg-white text-brand shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <button className="p-3 bg-white border border-slate-100 rounded-3xl text-slate-500 hover:text-brand transition-all shadow-sm">
              <TrendingUp className="w-5 h-5" />
            </button>
            <button className="px-6 py-3 bg-brand text-white rounded-3xl text-sm font-bold hover:bg-brand-hover transition-all shadow-lg shadow-brand/20 flex items-center">
              <RefreshCw className="w-5 h-5 mr-2" />
              同步ERP客户数据
            </button>
          </div>
        </div>

        {/* Bottom: Two-Column Layout */}
        <div className="flex-1 grid grid-cols-12 gap-6 overflow-hidden">
          
          {/* Left: AI Chat Dialog (col-span-4) */}
          <div className="col-span-4 flex flex-col bg-white/60 backdrop-blur-xl border border-white/80 rounded-3xl shadow-sm overflow-hidden">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center">
                <div className="w-10 h-10 bg-brand/10 rounded-3xl flex items-center justify-center mr-3">
                  <Sparkles className="w-6 h-6 text-brand" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">AI 健康助手</h3>
                  <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">实时决策支持</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                <span className="text-[10px] font-bold text-emerald-500">在线</span>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-4 custom-scrollbar">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] p-4 rounded-3xl text-sm leading-relaxed ${
                    msg.role === 'user' 
                      ? 'bg-brand text-white shadow-md shadow-brand/10' 
                      : 'bg-white border border-slate-100 text-slate-700 shadow-sm'
                  }`}>
                    {msg.content}
                    
                    {msg.type === 'dashboard' && msg.customer && (
                      <div className="mt-4 bg-slate-50 rounded-2xl p-4 border border-slate-100 text-slate-900 space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-3">
                            <div className="w-10 h-10 bg-brand rounded-xl flex items-center justify-center text-white font-bold">
                              {msg.customer.avatar}
                            </div>
                            <div>
                              <div className="font-bold">{msg.customer.name}</div>
                              <div className="text-[10px] text-slate-400">{msg.customer.status}</div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-[10px] text-slate-400 uppercase">风险指数</div>
                            <div className="text-xs font-bold text-red-500">{msg.customer.risk}</div>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="bg-white p-2 rounded-lg border border-slate-100">
                            <div className="text-[10px] text-slate-400">当前血压</div>
                            <div className="text-sm font-bold">{msg.customer.bp}</div>
                          </div>
                          <div className="bg-white p-2 rounded-lg border border-slate-100">
                            <div className="text-[10px] text-slate-400">消耗进度</div>
                            <div className="text-sm font-bold text-brand">{msg.customer.consumption}%</div>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setSelectedCustomer(msg.customer!)}
                          className="w-full py-2 bg-brand text-white rounded-3xl text-xs font-bold hover:bg-brand-hover transition-all shadow-sm flex items-center justify-center"
                        >
                          <Activity className="w-3 h-3 mr-2" />
                          添加至工作台并查看详情
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="p-5 border-t border-slate-100 bg-slate-50/30">
              <div className="flex flex-wrap gap-2 mb-3">
                {['查询张晓彤状态', '同步ERP数据', '生成随访计划'].map(q => (
                  <button 
                    key={q}
                    onClick={() => handleSendMessage(q)}
                    className="px-3 py-1.5 bg-white border border-slate-200 rounded-full text-[10px] font-bold text-slate-500 hover:border-brand hover:text-brand transition-all shadow-sm"
                  >
                    {q}
                  </button>
                ))}
              </div>
              <div className="relative">
                <input 
                  type="text" 
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder="输入指令或咨询问题..." 
                  className="w-full bg-white border border-slate-200 rounded-3xl py-3 pl-4 pr-12 text-sm focus:outline-none focus:border-brand/30 transition-all shadow-sm"
                />
                <button
                  type="button"
                  onClick={handleSendMessage}
                  aria-label="发送健康助手消息"
                  className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 bg-brand text-white rounded-3xl flex items-center justify-center hover:bg-brand-hover transition-all"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Right: Customer List (col-span-8) */}
          <div className="col-span-8 bg-white/60 backdrop-blur-xl border border-white/80 rounded-3xl overflow-hidden flex flex-col shadow-sm">
            <div className="px-8 py-5 border-b border-slate-50 bg-slate-50/30 grid grid-cols-12 gap-4 text-xs font-bold text-slate-400 uppercase tracking-wider">
              <div className="col-span-4">客户基本信息</div>
              <div className="col-span-3">当前状态</div>
              <div className="col-span-3">健康指标 & 风险</div>
              <div className="col-span-2 text-right">操作</div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar">
              {MOCK_CUSTOMERS.map((customer, idx) => (
                <motion.button
                  type="button"
                  key={customer.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.04 }}
                  onClick={() => setSelectedCustomer(customer)}
                  className="px-8 py-6 grid w-full grid-cols-12 gap-4 items-center hover:bg-brand/[0.02] transition-all border-b border-slate-50/50 group relative text-left"
                >
                  <div className="absolute left-0 top-0 bottom-0 w-1 bg-brand scale-y-0 group-hover:scale-y-100 transition-transform origin-center"></div>
                  
                  <div className="col-span-4 flex items-center space-x-4">
                    <div className="w-12 h-12 bg-gradient-to-br from-brand to-brand-hover rounded-3xl flex items-center justify-center text-white text-lg font-bold shadow-lg shadow-brand/10 group-hover:rotate-3 transition-all">
                      {customer.avatar}
                    </div>
                    <div className="min-w-0">
                      <h4 className="text-base font-bold text-slate-900 group-hover:text-brand transition-colors truncate">{customer.name}</h4>
                      <p className="text-xs text-slate-500 mt-0.5 truncate">{customer.theme}</p>
                    </div>
                  </div>

                  <div className="col-span-3">
                    <span className="inline-flex items-center px-2.5 py-1 bg-slate-50 text-slate-600 text-[10px] font-bold rounded-3xl border border-slate-100">
                      <div className="w-1.5 h-1.5 rounded-full bg-slate-300 mr-1.5"></div>
                      {customer.status}
                    </span>
                  </div>

                  <div className="col-span-3">
                    <div className="flex items-center space-x-4">
                      <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">血压</span>
                        <span className="text-xs font-bold text-slate-900">{customer.bp}</span>
                      </div>
                      <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">风险</span>
                        <span className={`text-xs font-bold ${customer.risk.includes('0.7') || customer.risk.includes('高压') ? 'text-red-500' : 'text-emerald-500'}`}>
                          {customer.risk}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="col-span-2 text-right">
                    <span className="p-2 bg-white border border-slate-100 text-brand rounded-3xl group-hover:bg-brand group-hover:text-white transition-all inline-flex">
                      <ChevronRight className="w-5 h-5" />
                    </span>
                  </div>
                </motion.button>
              ))}
            </div>

            {/* Pagination Footer */}
            <div className="px-8 py-4 border-t border-slate-100 bg-slate-50/30 flex items-center justify-between">
              <div className="text-xs font-bold text-slate-400">
                共 <span className="text-slate-900">128</span> 位客户
              </div>
              <div className="flex items-center space-x-1">
                {[1, 2, 3].map((page) => (
                  <button 
                    key={page} 
                    className={`w-7 h-7 rounded-3xl text-xs font-bold transition-all ${page === 1 ? 'bg-brand text-white shadow-sm' : 'text-slate-500 hover:bg-white'}`}
                  >
                    {page}
                  </button>
                ))}
                <button className="p-2 bg-white border border-slate-100 rounded-3xl text-slate-400 hover:text-brand transition-all">
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Top Bar with Back Button */}
      <div className="flex items-center justify-between bg-white/40 backdrop-blur-xl p-4 rounded-3xl border border-white/60">
        <button 
          onClick={() => setSelectedCustomer(null)}
          className="flex items-center text-slate-600 hover:text-brand transition-colors font-bold text-sm"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          返回客户列表
        </button>
        <div className="flex items-center space-x-4">
          <span className="text-xs text-slate-400 font-bold">当前正在处理：{selectedCustomer.name} 的健康数据</span>
          <div className="w-8 h-8 bg-brand rounded-3xl flex items-center justify-center text-white text-xs font-bold">
            {selectedCustomer.avatar}
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-6 flex-1 overflow-hidden">
        
        {/* A区: AI COPILOT */}
        <div className="col-span-3 flex flex-col space-y-4 overflow-hidden">
          <div className="bg-white/40 backdrop-blur-xl border border-white/60 rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex-1 flex flex-col overflow-hidden">
            <div className="p-6 border-b border-slate-100">
              <div className="text-xs font-bold text-slate-400 uppercase mb-1">A区 · AI COPILOT</div>
              <h3 className="text-xl font-bold text-slate-900">当前客户：{selectedCustomer.name} · {selectedCustomer.status}</h3>
              <div className="flex flex-wrap gap-2 mt-3">
                {selectedCustomer.tags.map(tag => (
                  <span key={tag} className="px-2 py-1 bg-brand/5 text-brand text-xs font-bold rounded-3xl border border-brand/10">
                    {tag}
                  </span>
                ))}
              </div>
              <div className="grid grid-cols-3 gap-2 mt-5">
                {['话术', '解读报告', '生成总结'].map(btn => (
                  <button key={btn} className="py-2.5 bg-slate-50 hover:bg-slate-100 text-slate-600 text-sm font-medium rounded-3xl border border-slate-200 transition-colors shadow-sm">
                    {btn}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex-1 p-6 overflow-y-auto space-y-5 custom-scrollbar">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[90%] p-4 rounded-3xl text-sm leading-relaxed ${
                    msg.role === 'user' 
                      ? 'bg-brand text-white shadow-md shadow-brand/10' 
                      : 'bg-white border border-slate-100 text-slate-700 shadow-sm'
                  }`}>
                    {msg.content}
                    
                    {msg.type === 'dashboard' && msg.customer && (
                      <div className="mt-4 bg-slate-50 rounded-2xl p-4 border border-slate-100 text-slate-900 space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-3">
                            <div className="w-10 h-10 bg-brand rounded-xl flex items-center justify-center text-white font-bold">
                              {msg.customer.avatar}
                            </div>
                            <div>
                              <div className="font-bold text-sm">{msg.customer.name}</div>
                              <div className="text-[10px] text-slate-400">{msg.customer.status}</div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-[10px] text-slate-400 uppercase">风险指数</div>
                            <div className="text-xs font-bold text-red-500">{msg.customer.risk}</div>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="bg-white p-2 rounded-lg border border-slate-100">
                            <div className="text-[10px] text-slate-400 flex items-center">
                              <Heart className="w-2 h-2 mr-1 text-red-500" />
                              当前血压
                            </div>
                            <div className="text-xs font-bold">{msg.customer.bp}</div>
                          </div>
                          <div className="bg-white p-2 rounded-lg border border-slate-100">
                            <div className="text-[10px] text-slate-400 flex items-center">
                              <Activity className="w-2 h-2 mr-1 text-brand" />
                              消耗进度
                            </div>
                            <div className="text-xs font-bold text-brand">{msg.customer.consumption}%</div>
                          </div>
                        </div>
                        <div className="bg-white p-2 rounded-lg border border-slate-100">
                          <div className="text-[10px] text-slate-400 flex items-center">
                            <Calendar className="w-2 h-2 mr-1 text-blue-500" />
                            最近回访
                          </div>
                          <div className="text-xs font-bold">{msg.customer.lastVisit}</div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setSelectedCustomer(msg.customer!)}
                          className="w-full py-2 bg-brand text-white rounded-3xl text-[10px] font-bold hover:bg-brand-hover transition-all shadow-sm flex items-center justify-center"
                        >
                          <Sparkles className="w-3 h-3 mr-2" />
                          添加至工作台并查看详情
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="p-6 border-t border-slate-100 bg-slate-50/30">
              <div className="relative">
                <textarea 
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSendMessage())}
                  placeholder="描述下一步指令或咨询问题..." 
                  className="w-full bg-white border border-slate-200 rounded-3xl p-4 pr-12 text-xs min-h-[100px] focus:outline-none focus:border-brand/30 transition-all resize-none shadow-sm"
                />
                <div className="absolute bottom-4 left-4 flex items-center space-x-4">
                  <button type="button" className="text-slate-400 hover:text-slate-600 transition-colors">
                    <Upload className="w-5 h-5" />
                  </button>
                </div>
                <div className="absolute bottom-4 right-4 flex items-center space-x-3">
                  <span className="text-[10px] text-slate-400 font-medium">上传报告</span>
                  <button
                    type="button"
                    onClick={() => handleSendMessage()}
                    aria-label="发送工作台消息"
                    className="w-10 h-10 bg-brand text-white rounded-3xl flex items-center justify-center hover:bg-brand-hover transition-all shadow-lg shadow-brand/20"
                  >
                    <Send className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* B区: 智能提醒 */}
        <div className="col-span-3 flex flex-col space-y-4 overflow-hidden">
          <div className="bg-white/40 backdrop-blur-xl border border-white/60 rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex-1 flex flex-col overflow-hidden p-6">
            <div className="mb-6">
              <div className="text-xs font-bold text-slate-400 uppercase mb-1">B区 · 智能提醒</div>
              <h3 className="text-xl font-bold text-slate-900">今日待办 · 随访计划</h3>
              <div className="flex space-x-2 mt-4">
                {['今日待办', '随访计划', '预警通知', '系统消息'].map((tab, i) => (
                  <button key={tab} className={`px-4 py-2 rounded-3xl text-xs font-bold transition-all ${i === 0 ? 'bg-brand text-white shadow-lg shadow-brand/20' : 'bg-white border border-slate-100 text-slate-500 hover:bg-slate-50'}`}>
                    {tab}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4 custom-scrollbar">
              <button type="button" className="w-full p-5 bg-white border border-slate-100 rounded-3xl hover:shadow-xl hover:-translate-y-1 transition-all group shadow-sm text-left">
                <div className="flex justify-between items-start mb-3">
                  <h4 className="text-base font-bold text-slate-900 group-hover:text-brand transition-colors">消耗提醒 · VIP{selectedCustomer.name}套餐7天后到期</h4>
                </div>
                <p className="text-sm text-slate-500 leading-relaxed mb-4">AI建议：本周安排2次营养调理，避免到期自动废度</p>
                <div className="flex items-center justify-between">
                  <span className="px-3 py-1 bg-red-50 text-red-500 text-xs font-bold rounded-3xl">优先级：紧急</span>
                  <span className="text-xs text-slate-400 flex items-center font-medium">
                    <Clock className="w-4 h-4 mr-1.5" /> 耗时10min
                  </span>
                </div>
              </button>

              <button type="button" className="w-full p-5 bg-white border border-slate-100 rounded-3xl hover:shadow-xl hover:-translate-y-1 transition-all group shadow-sm text-left">
                <div className="flex justify-between items-start mb-3">
                  <h4 className="text-base font-bold text-slate-900 group-hover:text-brand transition-colors">随访执行 · 09:30 呼叫{selectedCustomer.name} D14</h4>
                </div>
                <p className="text-sm text-slate-500 leading-relaxed mb-4">AI话术已生成，建议电话+企微触达</p>
                <div className="flex items-center justify-between">
                  <span className="px-3 py-1 bg-blue-50 text-blue-500 text-xs font-bold rounded-3xl">优先级：重要</span>
                  <span className="text-xs text-slate-400 flex items-center font-medium">
                    <Clock className="w-4 h-4 mr-1.5" /> 超时+2h
                  </span>
                </div>
              </button>

              <button type="button" className="w-full p-5 bg-white border border-slate-100 rounded-3xl hover:shadow-xl hover:-translate-y-1 transition-all group opacity-60 shadow-sm text-left">
                <div className="flex justify-between items-start mb-3">
                  <h4 className="text-base font-bold text-slate-900 group-hover:text-brand transition-colors">系统消息 · 版本 v0.9.12 推送</h4>
                </div>
                <p className="text-sm text-slate-500 leading-relaxed mb-3">更新：Copilot 新增语音摘要、C区布局收藏</p>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-400 group-hover:text-slate-600">阅读后标记</span>
                  <span className="text-xs text-slate-400 font-medium">08:10</span>
                </div>
              </button>
            </div>
          </div>
        </div>

        {/* C区: AI卡片工作流 */}
        <div className="col-span-3 flex flex-col space-y-4 overflow-hidden">
          <div className="bg-white/40 backdrop-blur-xl border border-white/60 rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex-1 flex flex-col overflow-hidden p-6">
            <div className="mb-6">
              <div className="text-xs font-bold text-slate-400 uppercase mb-1">C区 · AI卡片工作流</div>
              <h3 className="text-xl font-bold text-slate-900">AI洞察、消耗规划、随访编排</h3>
            </div>

            <div className="flex-1 overflow-y-auto space-y-6 custom-scrollbar">
              {/* AI Work Brief */}
              <div className="p-6 bg-white border border-slate-100 rounded-3xl shadow-sm relative overflow-hidden group hover:shadow-xl transition-all">
                <div className="absolute top-0 right-0 p-4 text-[10px] font-bold text-slate-300">任务悬浮</div>
                <div className="text-xs font-bold text-brand mb-3 tracking-wider">AI WORK BRIEF</div>
                <h4 className="text-2xl font-bold text-slate-900 mb-8">今日工作重点：聚耗+术后随访</h4>
                
                <div className="grid grid-cols-2 gap-8">
                  <div>
                    <div className="text-xs font-bold text-slate-400 mb-2">KPI完成率</div>
                    <div className="flex items-baseline space-x-2">
                      <span className="text-3xl font-bold text-slate-900">82%</span>
                      <span className="text-xs font-bold text-brand">+12%</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-400 mb-2">风险客户</div>
                    <div className="flex items-baseline space-x-2">
                      <span className="text-3xl font-bold text-orange-500">5</span>
                      <span className="text-xs font-bold text-orange-500">需触达</span>
                    </div>
                  </div>
                </div>
                
                <div className="mt-8 pt-5 border-t border-slate-50 flex flex-col space-y-2 text-sm text-slate-500 leading-relaxed">
                  <p>AI基于B区提醒与D区客户队列，预估耗时210分钟。</p>
                  <p className="font-bold text-brand">18:00前完成随访可自动生成周报</p>
                </div>
              </div>

              {/* AI随访编排 */}
              <div className="grid grid-cols-1 gap-4">
                <div className="p-5 bg-white border border-slate-100 rounded-3xl shadow-sm hover:shadow-xl transition-all">
                  <h5 className="text-base font-bold text-slate-900 mb-3">AI随访编排</h5>
                  <p className="text-xs text-slate-400 mb-5 leading-relaxed">本周12个术后随访按优先级排序，成功率预测 72%</p>
                  <div className="space-y-3 mb-6">
                    <div className="flex justify-between text-xs font-medium">
                      <span className="text-slate-600">{selectedCustomer.name}(紧急)</span>
                      <span className="text-slate-400">语音+企微</span>
                    </div>
                    <div className="flex justify-between text-xs font-medium">
                      <span className="text-slate-600">王曼曼(普通)</span>
                      <span className="text-slate-400">企微</span>
                    </div>
                    <div className="flex justify-between text-xs font-bold text-brand">
                      <span>赵心语(VIP)</span>
                      <span>视频</span>
                    </div>
                  </div>
                  <button className="w-full py-3 bg-brand text-white text-sm font-bold rounded-3xl hover:bg-brand-hover transition-all shadow-lg shadow-brand/20">
                    同步至B区
                  </button>
                </div>

                <div className="p-5 bg-white border border-slate-100 rounded-3xl shadow-sm hover:shadow-xl transition-all">
                  <h5 className="text-base font-bold text-slate-900 mb-3">套餐消耗规划</h5>
                  <p className="text-xs text-slate-400 mb-5 leading-relaxed">23个套餐存在到期风险，AI自动编排至4月10日前消完</p>
                  <div className="mb-5">
                    <div className="flex justify-between text-xs font-bold mb-2">
                      <span className="text-slate-500">本周执行：18/30</span>
                      <span className="text-brand">60%</span>
                    </div>
                    <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-brand w-[60%] shadow-[0_0_8px_rgba(59,130,246,0.3)]"></div>
                    </div>
                  </div>
                  <div className="text-xs font-bold text-slate-400">到期风险：23 套 · 已干预：8 套</div>
                </div>
              </div>

              {/* AI客户洞察 */}
              <div className="p-5 bg-white border border-slate-100 rounded-3xl shadow-sm hover:shadow-xl transition-all">
                <h5 className="text-base font-bold text-slate-900 mb-3">AI客户洞察</h5>
                <p className="text-xs text-slate-400 mb-5">结合L6运营索引，识别高流失概率客户并输出建议</p>
                <div className="space-y-4 mb-6">
                  <div className="flex items-start">
                    <span className="text-brand font-bold text-xs mr-3 mt-0.5">1.</span>
                    <p className="text-xs text-slate-700 leading-relaxed"><span className="font-bold">VIP{selectedCustomer.name}：</span>套餐消耗率{selectedCustomer.consumption}%，建议安排营养调理</p>
                  </div>
                  <div className="flex items-start">
                    <span className="text-brand font-bold text-xs mr-3 mt-0.5">2.</span>
                    <p className="text-xs text-slate-700 leading-relaxed"><span className="font-bold">金卡陈妍：</span>近30天0互动，推荐关怀+内容生成</p>
                  </div>
                </div>
                <div className="flex space-x-6">
                  <button className="text-xs font-bold text-brand hover:underline">一键转为激活计划</button>
                  <button className="text-xs font-bold text-slate-400 hover:underline">下载报告</button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* D区: 客户360视图 */}
        <div className="col-span-3 flex flex-col space-y-4 overflow-hidden">
          <div className="bg-white/40 backdrop-blur-xl border border-white/60 rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex-1 flex flex-col overflow-hidden p-8">
            <div className="mb-8">
              <div className="text-xs font-bold text-slate-400 uppercase mb-6">D区 · 客户360视图</div>
              <div className="flex items-center space-x-5">
                <div className="w-20 h-20 bg-brand rounded-3xl flex items-center justify-center text-white text-3xl font-bold shadow-xl shadow-brand/20">
                  {selectedCustomer.avatar}
                </div>
                <div>
                  <h3 className="text-2xl font-bold text-slate-900">{selectedCustomer.name} · VIP</h3>
                  <p className="text-sm text-slate-500 mt-2">健康主题：{selectedCustomer.theme} · 消耗率{selectedCustomer.consumption}%</p>
                  <div className="flex flex-wrap gap-2 mt-3">
                    <span className="px-2.5 py-1 bg-blue-50 text-blue-500 text-xs font-bold rounded-3xl">指标监测</span>
                    <span className="px-2.5 py-1 bg-orange-50 text-orange-500 text-xs font-bold rounded-3xl">{selectedCustomer.risk}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-10 custom-scrollbar">
              <section>
                <h5 className="text-sm font-bold text-slate-900 mb-5 flex items-center">
                  <div className="w-1 h-4 bg-brand rounded-full mr-2"></div>
                  健康档案
                </h5>
                <ul className="space-y-4">
                  <li className="flex items-center text-sm text-slate-700 font-medium">
                    <div className="w-2 h-2 rounded-full bg-brand mr-4"></div>
                    血压 {selectedCustomer.bp} (上次 {selectedCustomer.lastBp})
                  </li>
                  <li className="flex items-center text-sm text-slate-700 font-medium">
                    <div className="w-2 h-2 rounded-full bg-brand mr-4"></div>
                    血脂 LDL {selectedCustomer.lipid}
                  </li>
                  <li className="flex items-center text-sm text-slate-700 font-medium">
                    <div className="w-2 h-2 rounded-full bg-brand mr-4"></div>
                    体重 {selectedCustomer.weight}
                  </li>
                </ul>
              </section>

              <section>
                <h5 className="text-sm font-bold text-slate-900 mb-6 flex items-center">
                  <div className="w-1 h-4 bg-brand rounded-full mr-2"></div>
                  服务旅程
                </h5>
                <div className="space-y-8 relative ml-3">
                  <div className="absolute left-[7px] top-2 bottom-2 w-[1px] bg-slate-100"></div>
                  
                  <div className="relative pl-8">
                    <div className="absolute left-0 top-1.5 w-3.5 h-3.5 rounded-full bg-brand border-2 border-white shadow-lg shadow-brand/20"></div>
                    <div className="text-xs font-bold text-slate-400 mb-1">2026-03-13</div>
                    <div className="text-sm font-bold text-slate-700">最近回访完成</div>
                  </div>

                  <div className="relative pl-8">
                    <div className="absolute left-0 top-1.5 w-3.5 h-3.5 rounded-full bg-white border-2 border-brand shadow-md"></div>
                    <div className="text-xs font-bold text-slate-400 mb-1">2026-03-16</div>
                    <div className="text-sm font-bold text-slate-700">健康报告上传</div>
                  </div>

                  <div className="relative pl-8">
                    <div className="absolute left-0 top-1.5 w-3.5 h-3.5 rounded-full bg-brand-hover border-2 border-white shadow-lg shadow-brand/20"></div>
                    <div className="text-xs font-bold text-slate-400 mb-1">2026-03-20</div>
                    <div className="text-sm font-bold text-brand">待执行：{selectedCustomer.theme}计划</div>
                  </div>
                </div>
              </section>

              <section>
                <div className="flex justify-between items-center mb-5">
                  <h5 className="text-sm font-bold text-slate-900 flex items-center">
                    <div className="w-1 h-4 bg-brand rounded-full mr-2"></div>
                    消费 & 套餐
                  </h5>
                  <span className="text-xs font-bold text-slate-400">余 45天</span>
                </div>
                <div className="mb-5">
                  <div className="flex justify-between text-xs font-bold mb-3">
                    <span className="text-slate-500">套餐消耗</span>
                    <span className="text-slate-900">{selectedCustomer.consumption}%</span>
                  </div>
                  <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-brand w-[38%] shadow-[0_0_12px_rgba(59,130,246,0.4)]" style={{ width: `${selectedCustomer.consumption}%` }}></div>
                  </div>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed italic font-medium">
                  AI建议：本周安排2次{selectedCustomer.theme}、1次心理疏导
                </p>
              </section>
            </div>
          </div>
        </div>

      </div>

      {/* Footer Status Bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-white/40 backdrop-blur-xl rounded-3xl border border-white/60 text-xs text-slate-400 font-bold">
        <div className="flex items-center space-x-6">
          <div className="flex items-center">
            <div className="w-2 h-2 rounded-full bg-brand mr-2.5 animate-pulse"></div>
            系统在线
          </div>
          <div className="flex items-center">
            <div className="w-2 h-2 rounded-full bg-blue-500 mr-2.5"></div>
            数据最新同步 08:40
          </div>
        </div>
        <div className="flex items-center space-x-8">
          <span>告警 0</span>
          <span>待部署 1</span>
          <span className="text-brand">AI服务健康</span>
        </div>
      </div>
    </div>
  );
}
