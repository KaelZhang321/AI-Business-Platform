// 统计区域：展示首页核心经营指标和阶段性数据摘要。
import React from 'react';
import { Activity, Settings, CheckSquare, BarChart2, Zap, Layers, TrendingUp, Bell, CheckSquare as CheckSquareIcon, Sparkles } from 'lucide-react';
import { NOTICES } from '../data/mockData';

function StatCard({ title, value, unit, trend, icon: Icon, trendUp }: { title: string, value: string, unit: string, trend: string, icon: any, trendUp?: boolean }) {
  return (
    <div className="bg-white p-4 rounded-2xl border border-slate-100 shadow-sm flex flex-col hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-3">
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">{title}</span>
        <div className="p-1.5 bg-brand-light rounded-lg">
          <Icon className="w-4 h-4 text-brand" />
        </div>
      </div>
      <div className="flex items-baseline space-x-1">
        <span className="text-2xl font-bold text-slate-900 tracking-tight">{value}</span>
        <span className="text-xs text-slate-500 font-bold">{unit}</span>
      </div>
      <div className={`text-[10px] mt-2 font-bold flex items-center ${trendUp ? 'text-brand' : 'text-slate-400'}`}>
        {trendUp && <TrendingUp className="w-3 h-3 mr-1" />}
        {trend}
      </div>
    </div>
  );
}

export function StatsSection() {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      {/* Left: AI Stats */}
      <section className="xl:col-span-1 bg-white/40 backdrop-blur-xl border border-white/60 rounded-[32px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-slate-900 flex items-center">
            <Activity className="w-5 h-5 mr-2 text-brand" />
            AI 效能统计
          </h2>
          <button className="p-1.5 text-slate-400 hover:text-brand hover:bg-brand-light rounded-xl transition-colors">
            <Settings className="w-4 h-4" />
          </button>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <StatCard title="今日处理" value="24" unit="项" trend="+12%" icon={CheckSquare} trendUp />
          <StatCard title="SOP 达标" value="98" unit="%" trend="+2%" icon={BarChart2} trendUp />
          <StatCard title="AI 节省" value="2.5" unit="h" trend="+0.5h" icon={Zap} trendUp />
          <StatCard title="跨系统调用" value="156" unit="次" trend="稳定" icon={Layers} />
        </div>
      </section>

      {/* Right: Notices */}
      <section className="xl:col-span-2 bg-white/40 backdrop-blur-xl border border-white/60 rounded-[32px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex flex-col">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-slate-900 flex items-center">
            <Bell className="w-5 h-5 mr-2 text-brand" />
            通知公告
          </h2>
          <button className="text-sm font-bold text-brand hover:text-brand-hover transition-colors">
            全部
          </button>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 flex-1">
          {NOTICES.map((notice) => (
            <div key={notice.id} className="group">
              <div className="flex justify-between items-start mb-3">
                <h3 className="text-base font-bold text-slate-900 group-hover:text-brand transition-colors leading-snug pr-4 cursor-pointer">{notice.title}</h3>
                {!notice.read && <span className="w-2 h-2 rounded-full bg-[#FF5F57] shrink-0 mt-1.5 shadow-[0_0_5px_rgba(255,95,87,0.5)]"></span>}
              </div>
              <div className="bg-brand-light/50 rounded-xl p-3.5 mb-3 border border-brand-border/50 group-hover:bg-brand-light transition-colors">
                <div className="flex items-center text-[10px] font-bold text-brand mb-1.5 uppercase tracking-wider">
                  <Sparkles className="w-3.5 h-3.5 mr-1" /> AI 摘要
                </div>
                <p className="text-sm text-slate-600 leading-relaxed line-clamp-2">
                  {notice.aiSummary}
                </p>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">{notice.date}</span>
                {!notice.read ? (
                  <button className="text-xs font-bold text-brand hover:text-brand-hover hover:underline">
                    标记已读
                  </button>
                ) : (
                  <span className="text-xs font-bold text-brand flex items-center">
                    <CheckSquareIcon className="w-3.5 h-3.5 mr-1" /> 已读
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
