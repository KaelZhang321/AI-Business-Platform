import { Filter, Search } from 'lucide-react';

export function WorkbenchHeader() {
  return (
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
        <button className="p-2 bg-white border border-slate-200 rounded-3xl hover:bg-slate-50" type="button">
          <Filter className="w-4 h-4 text-slate-600" />
        </button>
      </div>
    </div>
  );
}
