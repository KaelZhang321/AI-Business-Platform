import { AlertTriangle, MessageSquare, TrendingUp, Zap } from 'lucide-react';

export function InsightsSidebar() {
  return (
    <div className="col-span-3 space-y-6 overflow-y-auto pr-2 custom-scrollbar">
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
  );
}
