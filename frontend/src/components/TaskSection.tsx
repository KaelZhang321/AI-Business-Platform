// 任务区：展示首页中的工作、待办和选中任务状态。
import React from 'react';
import { 
  ArrowUpDown, SlidersHorizontal, ChevronRight, Plus, 
  MessageSquareText, Paperclip 
} from 'lucide-react';
import { WORKS, TODOS } from '../data/mockData';

/** 任务区组件属性 */
interface TaskSectionProps {
  /** 当前活动页签 */
  activeTab: 'work' | 'todo' | 'risk';
  /** 切换页签 */
  setActiveTab: (tab: 'work' | 'todo' | 'risk') => void;
  /** 当前选中任务 ID */
  selectedTaskId: number | null;
  /** 设置选中任务 */
  setSelectedTaskId: (id: number | null) => void;
  /** 打开创建任务弹窗 */
  setIsCreateModalOpen: (open: boolean) => void;
}

/** 任务区组件：展示首页中的工作、待办列表和新建任务入口 */
export function TaskSection({ 
  activeTab, 
  setActiveTab, 
  selectedTaskId, 
  setSelectedTaskId, 
  setIsCreateModalOpen 
}: TaskSectionProps) {
  /** 根据当前页签切换数据源 */
  const currentTasks = activeTab === 'work' ? WORKS : TODOS;

  return (
    <section className="xl:col-span-3 bg-white/40 backdrop-blur-xl border border-white/60 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex flex-col dark:bg-slate-900/60 dark:border-slate-700/60">
      <div className="flex items-center justify-between mb-6 border-b border-slate-100 pb-4 dark:border-slate-700">
        <div className="flex items-center space-x-8">
          <button 
            onClick={() => setActiveTab('work')}
            className={`text-lg font-bold flex items-center transition-colors relative ${activeTab === 'work' ? 'text-slate-900 dark:text-slate-100' : 'text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300'}`}
          >
            我的工作
          </button>
          <button 
            onClick={() => setActiveTab('todo')}
            className={`text-lg font-bold flex items-center transition-colors relative ${activeTab === 'todo' ? 'text-slate-900 dark:text-slate-100' : 'text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300'}`}
          >
            待办事项
            <span className="ml-2 bg-[#FF5F57] text-white text-[10px] px-1.5 py-0.5 rounded-full leading-none shadow-sm">3</span>
          </button>
        </div>
        <div className="flex items-center space-x-3">
          <button className="flex items-center px-3 py-1.5 bg-slate-50 text-slate-600 text-sm font-medium rounded-xl hover:bg-slate-100 transition-colors border border-slate-200 shadow-sm dark:bg-slate-800 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-700">
            <ArrowUpDown className="w-4 h-4 mr-1.5 text-slate-400 dark:text-slate-500" />
            排序
            <ChevronRight className="w-3 h-3 ml-1.5 rotate-90 text-slate-400 dark:text-slate-500" />
          </button>
          <button className="flex items-center px-3 py-1.5 bg-slate-50 text-slate-600 text-sm font-medium rounded-xl hover:bg-slate-100 transition-colors border border-slate-200 shadow-sm dark:bg-slate-800 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-700">
            <SlidersHorizontal className="w-4 h-4 mr-1.5 text-slate-400 dark:text-slate-500" />
            筛选
            <ChevronRight className="w-3 h-3 ml-1.5 rotate-90 text-slate-400 dark:text-slate-500" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 relative z-10 items-start">
        {currentTasks.map(todo => {
          const isSelected = selectedTaskId === todo.id;
          
          return (
            <button
              type="button"
              key={todo.id} 
              onClick={() => setSelectedTaskId(isSelected ? null : todo.id)}
              aria-pressed={isSelected}
              className={`group flex flex-col p-5 rounded-2xl bg-white border border-slate-100 cursor-pointer transition-all duration-300 dark:bg-slate-900 dark:border-slate-700 ${
                isSelected 
                  ? 'shadow-[0_20px_40px_-15px_rgba(0,0,0,0.1)] scale-105 z-20 ring-1 ring-slate-200 rotate-1 dark:ring-slate-600' 
                  : 'shadow-sm hover:shadow-md hover:-translate-y-1 z-10 dark:hover:shadow-slate-950/30'
              } text-left`}
            >
              <div className="flex flex-col mb-4">
                <h3 className="text-base font-bold text-slate-900 mb-1 leading-tight dark:text-slate-100">
                  {todo.title}
                </h3>
                <div className="text-xs text-slate-400 font-medium dark:text-slate-500">
                  {todo.timeRange}
                </div>
              </div>

              <div className="bg-slate-50/50 rounded-xl p-3 mb-4 border border-slate-100 dark:bg-slate-800/70 dark:border-slate-700">
                <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1 dark:text-slate-400">任务描述</div>
                <p className="text-sm text-slate-600 leading-relaxed line-clamp-2 dark:text-slate-300">
                  {todo.description}
                </p>
              </div>

              <div className="flex items-center justify-between mb-4">
                <div className="flex -space-x-2">
                  {todo.assignees?.map((avatar) => (
                    <img key={avatar} src={avatar} alt="任务执行人头像" className="w-7 h-7 rounded-full border-2 border-white shadow-sm" />
                  ))}
                </div>
                <div className="flex items-center space-x-3 text-slate-400 dark:text-slate-500">
                  <div className="flex items-center text-xs font-medium">
                    <MessageSquareText className="w-4 h-4 mr-1" />
                    {todo.comments || 0}
                  </div>
                  <div className="flex items-center text-xs font-medium">
                    <Paperclip className="w-4 h-4 mr-1" />
                    {todo.attachments || 0}
                  </div>
                </div>
              </div>

              <div className="mt-auto pt-2 flex flex-col space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-wider dark:text-slate-400">执行进度</span>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-slate-900 dark:text-slate-100">{todo.progress}%</span>
                    <span className="px-3 py-1 bg-brand text-white text-[10px] font-bold rounded-full shadow-sm">
                      去完成
                    </span>
                  </div>
                </div>
                <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden dark:bg-slate-700">
                  <div 
                    className={`h-full rounded-full transition-all duration-500 ${todo.progress > 80 ? 'bg-brand' : todo.progress > 40 ? 'bg-orange-400' : 'bg-red-400'}`}
                    style={{ width: `${todo.progress}%` }}
                  ></div>
                </div>
              </div>
            </button>
          );
        })}

        <button
          type="button"
          onClick={() => setIsCreateModalOpen(true)}
          className="group flex flex-col items-center justify-center p-8 rounded-2xl bg-slate-50/50 border-2 border-dashed border-slate-200 cursor-pointer hover:bg-white hover:border-brand/40 transition-all duration-300 min-h-[280px] dark:bg-slate-800/60 dark:border-slate-700 dark:hover:bg-slate-800"
        >
          <div className="w-12 h-12 rounded-2xl bg-white border border-slate-200 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform shadow-sm group-hover:shadow-md group-hover:border-brand/20 dark:bg-slate-900 dark:border-slate-600">
            <Plus className="w-6 h-6 text-slate-400 group-hover:text-brand dark:text-slate-500" />
          </div>
          <span className="text-sm font-bold text-slate-500 group-hover:text-brand dark:text-slate-400">新建任务</span>
          <p className="text-xs text-slate-400 mt-2 text-center dark:text-slate-500">点击添加新的工作或待办事项</p>
        </button>
      </div>
    </section>
  );
}
