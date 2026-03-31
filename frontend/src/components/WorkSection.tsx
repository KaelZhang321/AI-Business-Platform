// 工作卡片区：以卡片形式呈现工作项或待办项的概览信息。
import React from 'react';
import { 
  ArrowUpDown, SlidersHorizontal, ChevronRight, MessageSquareText, 
  Paperclip, Plus 
} from 'lucide-react';
import { Work, Todo } from '../types';

interface WorkSectionProps {
  activeTab: 'work' | 'todo' | 'risk';
  setActiveTab: (tab: 'work' | 'todo' | 'risk') => void;
  works: Work[];
  todos: Todo[];
  selectedTaskId: number | null;
  setSelectedTaskId: (id: number | null) => void;
  setIsCreateModalOpen: (val: boolean) => void;
}

export function WorkSection({ 
  activeTab, 
  setActiveTab, 
  works, 
  todos, 
  selectedTaskId, 
  setSelectedTaskId,
  setIsCreateModalOpen
}: WorkSectionProps) {
  const currentData = activeTab === 'work' ? works : todos;

  return (
    <section className="xl:col-span-3 bg-white/40 backdrop-blur-xl border border-white/60 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex flex-col">
      <div className="flex items-center justify-between mb-6 border-b border-slate-100 pb-4">
        <div className="flex items-center space-x-8">
          <button 
            onClick={() => setActiveTab('work')}
            className={`text-lg font-bold flex items-center transition-colors relative ${activeTab === 'work' ? 'text-slate-800' : 'text-slate-400 hover:text-slate-600'}`}
          >
            我的工作
          </button>
          <button 
            onClick={() => setActiveTab('todo')}
            className={`text-lg font-bold flex items-center transition-colors relative ${activeTab === 'todo' ? 'text-slate-800' : 'text-slate-400 hover:text-slate-600'}`}
          >
            待办事项
            <span className="ml-2 bg-red-500 text-white text-[10px] px-1.5 py-0.5 rounded-full leading-none">3</span>
          </button>
        </div>
        <div className="flex items-center space-x-3">
          <button className="flex items-center px-3 py-1.5 bg-slate-50 text-slate-600 text-sm font-medium rounded-lg hover:bg-slate-100 transition-colors border border-slate-200 shadow-sm">
            <ArrowUpDown className="w-4 h-4 mr-1.5 text-slate-400" />
            排序
            <ChevronRight className="w-3 h-3 ml-1.5 rotate-90 text-slate-400" />
          </button>
          <button className="flex items-center px-3 py-1.5 bg-slate-50 text-slate-600 text-sm font-medium rounded-lg hover:bg-slate-100 transition-colors border border-slate-200 shadow-sm">
            <SlidersHorizontal className="w-4 h-4 mr-1.5 text-slate-400" />
            筛选
            <ChevronRight className="w-3 h-3 ml-1.5 rotate-90 text-slate-400" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 relative z-10 items-start">
        {currentData.map(todo => {
          const isSelected = selectedTaskId === todo.id;
          
          return (
            <button
              type="button"
              key={todo.id} 
              onClick={() => setSelectedTaskId(isSelected ? null : todo.id)}
              aria-pressed={isSelected}
              className={`group flex flex-col p-5 rounded-2xl bg-white border border-slate-100 cursor-pointer transition-all duration-300 ${
                isSelected 
                  ? 'shadow-[0_20px_40px_-15px_rgba(0,0,0,0.1)] scale-105 z-20 ring-1 ring-slate-200 rotate-1' 
                  : 'shadow-sm hover:shadow-md hover:-translate-y-1 z-10'
              } text-left`}
            >
              <div className="flex flex-col mb-4">
                <h3 className="text-[16px] font-bold text-slate-800 mb-1 leading-tight">
                  {todo.title}
                </h3>
                <div className="text-[13px] text-slate-400 font-medium">
                  {todo.timeRange}
                </div>
              </div>

              <div className="bg-[#F8FAFC] rounded-xl p-3 mb-4">
                <div className="text-[12px] font-bold text-slate-500 mb-1">Description</div>
                <p className="text-[13px] text-slate-500 leading-relaxed">
                  {todo.description}
                </p>
              </div>

              <div className="flex items-center justify-between mb-4">
                <div className="flex -space-x-2">
                  {todo.assignees?.map((avatar) => (
                    <img key={avatar} src={avatar} alt="任务执行人头像" className="w-7 h-7 rounded-full border-2 border-white shadow-sm" />
                  ))}
                </div>
                <div className="flex items-center space-x-3 text-slate-400">
                  <div className="flex items-center text-[12px] font-medium">
                    <MessageSquareText className="w-4 h-4 mr-1" />
                    {todo.comments || 0}
                  </div>
                  <div className="flex items-center text-[12px] font-medium">
                    <Paperclip className="w-4 h-4 mr-1" />
                    {todo.attachments || 0}
                  </div>
                </div>
              </div>

              <div className="mt-auto pt-2 flex flex-col space-y-2">
                <div className="flex justify-between items-end">
                  <span className="text-[13px] font-bold text-slate-700">Task progress</span>
                  <span className="text-[14px] font-bold text-slate-800">{todo.progress}%</span>
                </div>
                <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div 
                    className={`h-full rounded-full ${todo.progress > 80 ? 'bg-brand' : todo.progress > 40 ? 'bg-orange-400' : 'bg-red-400'}`}
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
          className="group flex flex-col items-center justify-center p-8 rounded-2xl bg-slate-50 border-2 border-dashed border-slate-200 cursor-pointer hover:bg-slate-100 hover:border-blue-300 transition-all duration-300 min-h-[280px]"
        >
          <div className="w-12 h-12 rounded-full bg-white border border-slate-200 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform shadow-sm">
            <Plus className="w-6 h-6 text-slate-400 group-hover:text-brand" />
          </div>
          <span className="text-sm font-bold text-slate-500 group-hover:text-brand">新建任务</span>
          <p className="text-xs text-slate-400 mt-2 text-center">点击添加新的工作或待办事项</p>
        </button>
      </div>
    </section>
  );
}
