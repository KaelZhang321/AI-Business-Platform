// 弹窗组件集合：集中管理接待登记、新建任务等弹窗内容。
import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, CheckSquare, UserCheck, HeartPulse, Briefcase, MessageSquareText, Sparkles, FileText, Users, Clock, CalendarClock, Paperclip, Plus } from 'lucide-react';

interface ReceptionModalProps {
  isOpen: boolean;
  onClose: () => void;
  form: { name: string; serial: string; details: string };
  setForm: (form: any) => void;
}

export function ReceptionModal({ isOpen, onClose, form, setForm }: ReceptionModalProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        >
          <motion.div 
            initial={{ scale: 0.95, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.95, opacity: 0, y: 20 }}
            className="bg-white rounded-3xl shadow-2xl w-full max-w-5xl overflow-hidden flex flex-col"
          >
            <div className="flex items-center justify-between p-6 border-b border-slate-100">
              <h2 className="text-xl font-bold text-slate-800">客户到院接待</h2>
              <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-8 overflow-y-auto max-h-[80vh]">
              <div className="bg-gradient-to-r from-[#F0F4FF] to-[#F8FAFC] rounded-2xl p-6 flex items-center justify-between border border-blue-50">
                <div>
                  <h3 className="text-xl font-bold text-blue-900 mb-1">客户到院接待</h3>
                  <p className="text-sm text-brand font-medium">办理客户签到、到院登记与房间分配</p>
                </div>
                <div className="bg-brand-light text-brand border border-brand-border rounded-full px-3 py-1.5 flex items-center text-sm font-medium shadow-sm">
                  <CheckSquare className="w-4 h-4 mr-1.5" />
                  AI 辅助已就绪
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
                <div className="border border-slate-100 rounded-2xl p-6 bg-white shadow-sm">
                  <div className="grid grid-cols-2 gap-4 mb-6">
                    <div>
                      <label className="block text-xs font-bold text-slate-400 mb-2">客户姓名</label>
                      <input 
                        type="text" 
                        value={form.name}
                        onChange={(e) => setForm({...form, name: e.target.value})}
                        className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm font-bold text-slate-800 focus:bg-white focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-400 mb-2">流水单号</label>
                      <input 
                        type="text" 
                        value={form.serial}
                        onChange={(e) => setForm({...form, serial: e.target.value})}
                        className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm font-mono text-slate-600 focus:bg-white focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-all"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-400 mb-2">业务处理细节</label>
                    <textarea 
                      value={form.details}
                      onChange={(e) => setForm({...form, details: e.target.value})}
                      rows={6}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-700 focus:bg-white focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-all resize-none"
                    ></textarea>
                  </div>
                </div>

                <div className="border border-slate-100 rounded-2xl p-6 bg-slate-50/50 shadow-inner flex flex-col">
                  <div className="flex items-center mb-6">
                    <MessageSquareText className="w-5 h-5 text-brand mr-2" />
                    <h3 className="text-base font-bold text-brand">AI 智能分析建议</h3>
                  </div>
                  
                  <div className="flex-1 border border-brand-border rounded-xl p-5 bg-white shadow-sm overflow-y-auto">
                    {form.name.includes('张三') ? (
                      <div className="space-y-4">
                        <div className="flex items-start">
                          <div className="w-8 h-8 rounded-full bg-brand-light flex items-center justify-center mr-3 shrink-0">
                            <UserCheck className="w-4 h-4 text-brand" />
                          </div>
                          <div>
                            <h4 className="text-sm font-bold text-slate-800 mb-1">VIP 客户识别</h4>
                            <p className="text-xs text-slate-600 leading-relaxed">
                              该客户为 A 级 VIP。历史偏好：<span className="font-semibold text-brand">独立静音休息室</span>、<span className="font-semibold text-brand">无糖绿茶</span>。建议优先安排 302 专属房间。
                            </p>
                          </div>
                        </div>
                        <div className="flex items-start">
                          <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center mr-3 shrink-0">
                            <HeartPulse className="w-4 h-4 text-orange-600" />
                          </div>
                          <div>
                            <h4 className="text-sm font-bold text-slate-800 mb-1">健康档案预警</h4>
                            <p className="text-xs text-slate-600 leading-relaxed">
                              客户有轻度高血压史。今日体检方案中包含<span className="font-semibold text-orange-600">心血管深度筛查</span>，请提醒护士在抽血前再次确认血压状态。
                            </p>
                          </div>
                        </div>
                        <div className="flex items-start">
                          <div className="w-8 h-8 rounded-full bg-brand-light flex items-center justify-center mr-3 shrink-0">
                            <Briefcase className="w-4 h-4 text-brand" />
                          </div>
                          <div>
                            <h4 className="text-sm font-bold text-slate-800 mb-1">关联业务提醒</h4>
                            <p className="text-xs text-slate-600 leading-relaxed">
                              客户上周咨询了“抗衰老基因检测”项目，当前尚未成单。建议在体检报告解读环节，由专属顾问适时引入该项目介绍。
                            </p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="h-full flex flex-col items-center justify-center text-slate-400">
                        <Sparkles className="w-8 h-8 mb-3 opacity-50" />
                        <p className="text-sm italic text-center">
                          输入客户信息后，AI 将自动检索画像<br/>并生成个性化接待建议
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end space-x-4 p-6 border-t border-slate-100 bg-slate-50/80">
              <button onClick={onClose} className="px-6 py-2.5 rounded-xl border border-slate-200 bg-white text-slate-600 font-bold hover:bg-slate-50 hover:text-slate-800 transition-colors shadow-sm">
                关 闭
              </button>
              <button onClick={onClose} className="px-6 py-2.5 rounded-xl bg-brand text-white font-bold hover:bg-brand-hover transition-colors shadow-md shadow-brand/20">
                确认办理
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

interface CreateTaskModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CreateTaskModal({ isOpen, onClose }: CreateTaskModalProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"
          />
          <motion.div 
            initial={{ scale: 0.9, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.9, opacity: 0, y: 20 }}
            className="relative w-full max-w-2xl bg-white rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
          >
            <div className="px-8 py-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-blue-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
                  <Plus className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-800">新建任务</h2>
                  <p className="text-xs text-slate-400">请填写任务详细信息以创建新任务</p>
                </div>
              </div>
              <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
                <X className="w-6 h-6 text-slate-400" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
              <form className="space-y-6">
                <div className="space-y-2">
                  <label className="text-sm font-bold text-slate-700 flex items-center">
                    <FileText className="w-4 h-4 mr-2 text-blue-500" />
                    任务名称
                  </label>
                  <input 
                    type="text" 
                    placeholder="请输入任务名称..."
                    className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-bold text-slate-700 flex items-center">
                    <MessageSquareText className="w-4 h-4 mr-2 text-blue-500" />
                    任务详情
                  </label>
                  <textarea 
                    rows={4}
                    placeholder="请描述任务的具体内容和要求..."
                    className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm resize-none"
                  ></textarea>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-bold text-slate-700 flex items-center">
                    <Users className="w-4 h-4 mr-2 text-blue-500" />
                    参与任务
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {['李调度', '王经理', '张专员', '赵财务'].map((name, i) => (
                      <button 
                        key={i}
                        type="button"
                        className="px-3 py-1.5 rounded-full border border-slate-200 text-xs font-medium text-slate-600 hover:bg-brand-light hover:border-brand-border hover:text-brand transition-all flex items-center"
                      >
                        <div className="w-5 h-5 rounded-full bg-slate-200 mr-2 overflow-hidden">
                          <img src={`https://i.pravatar.cc/150?u=${i+20}`} alt="" className="w-full h-full object-cover" />
                        </div>
                        {name}
                      </button>
                    ))}
                    <button type="button" className="w-8 h-8 rounded-full border-2 border-dashed border-slate-200 flex items-center justify-center text-slate-400 hover:border-brand-border hover:text-brand transition-all">
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-slate-700 flex items-center">
                      <Clock className="w-4 h-4 mr-2 text-blue-500" />
                      计划开始
                    </label>
                    <input 
                      type="datetime-local" 
                      className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-slate-700 flex items-center">
                      <CalendarClock className="w-4 h-4 mr-2 text-blue-500" />
                      完成时间
                    </label>
                    <input 
                      type="datetime-local" 
                      className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-bold text-slate-700 flex items-center">
                    <Paperclip className="w-4 h-4 mr-2 text-blue-500" />
                    上传附件
                  </label>
                  <div className="border-2 border-dashed border-slate-200 rounded-2xl p-8 flex flex-col items-center justify-center hover:bg-slate-50 transition-colors cursor-pointer group">
                    <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mb-3 group-hover:bg-blue-50 transition-colors">
                      <Plus className="w-6 h-6 text-slate-400 group-hover:text-blue-500" />
                    </div>
                    <span className="text-sm font-medium text-slate-500">点击或拖拽文件到此处上传</span>
                    <p className="text-xs text-slate-400 mt-1">支持 PDF, Word, Excel, 图片等格式</p>
                  </div>
                </div>
              </form>
            </div>

            <div className="px-8 py-6 border-t border-slate-100 flex items-center justify-end space-x-4 bg-slate-50/50">
              <button onClick={onClose} className="px-6 py-2.5 rounded-xl text-sm font-bold text-slate-500 hover:bg-slate-100 transition-colors">
                取消
              </button>
              <button onClick={onClose} className="px-8 py-2.5 rounded-xl text-sm font-bold text-white bg-brand hover:bg-brand-hover shadow-lg shadow-brand/30 transition-all active:scale-95">
                确认创建
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
