import { Activity, Brain, Download, RefreshCw } from 'lucide-react';

export function CustomerInfoBar() {
  return (
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
  );
}
