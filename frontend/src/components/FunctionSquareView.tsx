// 功能广场视图：展示推荐模块、全部功能以及导航跳转入口。
import React from 'react';
import { motion } from 'motion/react';
import { Search, ChevronRight, Star } from 'lucide-react';
import { FUNCTION_MODULES } from '../data/mockData';
import type { AppPage } from '../navigation';

/** 功能广场视图组件属性 */
interface FunctionSquareViewProps {
  /** 页面切换回调 */
  setCurrentPage: (page: AppPage) => void;
}

/** 功能广场视图组件：展示最新上线、推荐功能和全部功能模块 */
export function FunctionSquareView({ setCurrentPage }: FunctionSquareViewProps) {
  /** 功能名称 → 页面标识的映射表（用于点击跳转） */
  const FEATURE_PAGE_MAP: Record<string, AppPage> = {
    'AI辅助诊断': 'ai-diagnosis',
    'AI报告对比': 'ai-report-comparison',
    'AI报告解读': 'ai-report-comparison',
    'AI四象限健康评估': 'ai-four-quadrant',
  };

  /** 点击模块卡片时跳转到对应页面 */
  const handleModuleClick = (title: string) => {
    const targetPage = FEATURE_PAGE_MAP[title];
    if (targetPage) {
      setCurrentPage(targetPage);
    }
  };

  return (
    <div className="space-y-10 pb-12">
      {/* Hero / Search Section */}
      <section className="relative py-16 px-8 rounded-[32px] overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-brand/10 via-brand/5 to-transparent -z-10"></div>
        <div className="absolute top-0 right-0 w-1/2 h-full bg-[url('https://images.unsplash.com/photo-1576091160550-2173dba999ef?auto=format&fit=crop&q=80&w=1200&h=800')] bg-cover bg-center opacity-10 -z-10 mix-blend-overlay"></div>
        
        <div className="max-w-3xl mx-auto text-center space-y-6">
          <h2 className="text-4xl font-bold text-slate-900 tracking-tight">
            探索解决方案 <span className="inline-block animate-bounce">🧐</span> 激发团队灵感
          </h2>
          <div className="relative max-w-2xl mx-auto">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
            <input 
              type="text" 
              placeholder="搜索功能、应用或解决方案..." 
              className="w-full pl-12 pr-4 py-4 bg-white border-none rounded-2xl shadow-xl shadow-brand/5 focus:ring-2 focus:ring-brand outline-none text-slate-800 text-lg transition-all"
            />
          </div>
        </div>
      </section>

      {/* Latest Features Section */}
      <section className="space-y-6">
        <div className="flex items-center justify-between px-2">
          <div>
            <h3 className="text-xl font-bold text-slate-900">最新上新功能</h3>
            <p className="text-sm text-slate-500 mt-1">通过AI赋能临床决策，解决诊断与方案规划核心挑战，提升医疗服务质量</p>
          </div>
          <button className="text-brand font-bold flex items-center hover:underline text-sm">
            查看全部 <ChevronRight className="w-4 h-4 ml-0.5" />
          </button>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {FUNCTION_MODULES.latest.map((item, idx) => (
            <motion.button
              type="button"
              key={item.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              aria-label={item.title}
              className="group bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-xl transition-all border border-slate-100 cursor-pointer text-left"
              onClick={() => handleModuleClick(item.title)}
            >
              <div className="relative h-40 overflow-hidden">
                <img 
                  src={item.icon} 
                  alt={item.title} 
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  referrerPolicy="no-referrer"
                />
                <div className="absolute top-3 left-3 px-2 py-1 bg-black/50 backdrop-blur-md text-white text-[10px] rounded-lg font-bold uppercase tracking-wider">
                  {item.tag}
                </div>
              </div>
              <div className="p-5 space-y-2">
                <h4 className="text-base font-bold text-slate-900 group-hover:text-brand transition-colors line-clamp-1">{item.title}</h4>
                <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">{item.desc}</p>
              </div>
            </motion.button>
          ))}
        </div>
      </section>

      {/* AI Recommended Section */}
      <section className="space-y-6">
        <div className="flex items-center justify-between px-2">
          <div>
            <h3 className="text-xl font-bold text-slate-900 flex items-center">
              AI 推荐功能 <span className="ml-2">👆</span>
            </h3>
            <p className="text-sm text-slate-500 mt-1">探索智能驾驶舱之上的医疗助手，提高诊疗效率，提升患者康复体验</p>
          </div>
          <button className="text-brand font-bold flex items-center hover:underline text-sm">
            查看全部 <ChevronRight className="w-4 h-4 ml-0.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {FUNCTION_MODULES.recommended.map((item, idx) => (
            <motion.button
              type="button"
              key={item.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.05 }}
              className="flex items-start p-4 bg-white rounded-2xl shadow-sm hover:shadow-md transition-all border border-slate-50 group cursor-pointer"
              aria-label={item.title}
              onClick={() => handleModuleClick(item.title)}
            >
              <div className="w-12 h-12 rounded-xl overflow-hidden shrink-0 mr-4 shadow-sm">
                <img src={item.icon} alt={item.title} className="w-full h-full object-cover" referrerPolicy="no-referrer" />
              </div>
              <div className="space-y-1 min-w-0">
                <div className="flex items-center space-x-2">
                  <h4 className="font-bold text-slate-900 text-sm group-hover:text-brand transition-colors truncate">{item.title}</h4>
                  <span className="px-1.5 py-0.5 bg-brand/10 text-brand text-[10px] rounded font-bold uppercase tracking-wider shrink-0">{item.tag}</span>
                </div>
                <p className="text-xs text-slate-500 line-clamp-1">{item.desc}</p>
              </div>
            </motion.button>
          ))}
        </div>
      </section>

      {/* All Features Section */}
      <section className="space-y-6">
        <div className="flex items-center justify-between px-2">
          <div>
            <h3 className="text-xl font-bold text-slate-900">全部功能</h3>
            <p className="text-sm text-slate-500 mt-1">汇聚辅助诊断、干预方案、病历生成、报告解读等全方位医疗AI工具</p>
          </div>
          <button className="text-brand font-bold flex items-center hover:underline text-sm">
            查看全部 <ChevronRight className="w-4 h-4 ml-0.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {FUNCTION_MODULES.all.map((item, idx) => (
            <motion.button
              type="button"
              key={item.id}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: idx * 0.05 }}
              className="flex items-start p-4 bg-white rounded-2xl shadow-sm hover:shadow-md transition-all border border-slate-50 group cursor-pointer"
              aria-label={item.title}
              onClick={() => handleModuleClick(item.title)}
            >
              <div className="w-12 h-12 rounded-xl overflow-hidden shrink-0 mr-4 shadow-sm">
                <img src={item.icon} alt={item.title} className="w-full h-full object-cover" referrerPolicy="no-referrer" />
              </div>
              <div className="space-y-1 min-w-0">
                <div className="flex items-center space-x-2">
                  <h4 className="font-bold text-slate-900 text-sm group-hover:text-brand transition-colors truncate">{item.title}</h4>
                  <span className="px-1.5 py-0.5 bg-slate-100 text-slate-500 text-[10px] rounded font-bold uppercase tracking-wider shrink-0">{item.tag}</span>
                </div>
                <p className="text-xs text-slate-500 line-clamp-1">{item.desc}</p>
              </div>
            </motion.button>
          ))}
        </div>
      </section>

      {/* Footer Banner */}
      <div className="bg-brand/5 rounded-[32px] p-8 flex flex-col md:flex-row items-center justify-between border border-brand/10">
        <div className="flex items-center space-x-4 mb-4 md:mb-0">
          <div className="text-3xl">🤔</div>
          <div>
            <h4 className="font-bold text-slate-900">没有找到合适的功能或方案？</h4>
            <p className="text-sm text-slate-500">提交需求，享专人服务</p>
          </div>
        </div>
        <button className="px-6 py-2.5 bg-brand text-white rounded-xl font-bold hover:bg-brand-hover transition-colors shadow-lg shadow-brand/20">
          提交需求
        </button>
      </div>
    </div>
  );
}
