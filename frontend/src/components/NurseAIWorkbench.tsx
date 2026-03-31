// 护士 AI 工作台：用于展示护理任务、预警信息和快捷护理操作。
import React from 'react';
import { motion } from 'motion/react';
import { 
  Activity, 
  Thermometer, 
  Droplets, 
  Clock, 
  AlertCircle, 
  CheckCircle2, 
  Bell, 
  User, 
  ChevronRight,
  Stethoscope,
  Heart,
  Zap,
  LayoutGrid,
  List,
  Search,
  Filter
} from 'lucide-react';

const WARD_TASKS = [
  { id: '1', patient: '张晓彤', bed: '01', task: '静脉输液', time: '10:30', status: '进行中', priority: '高' },
  { id: '2', patient: '李建国', bed: '05', task: '生命体征测量', time: '11:00', status: '待执行', priority: '中' },
  { id: '3', patient: '王芳', bed: '08', task: '术后伤口换药', time: '11:15', status: '待执行', priority: '高' },
  { id: '4', patient: '赵强', bed: '12', task: '口服药发放', time: '11:30', status: '待执行', priority: '低' },
];

const VITAL_ALERTS = [
  { patient: '李建国', bed: '05', type: '心率', value: '112 bpm', time: '3分钟前', level: '警告' },
  { patient: '王芳', bed: '08', type: '体温', value: '38.5 ℃', time: '10分钟前', level: '注意' },
];

export function NurseAIWorkbench() {
  return (
    <div className="h-full flex flex-col space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">护士AI工作台</h2>
          <p className="text-sm text-slate-500">智能护理协作，守护患者安全</p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input 
              type="text" 
              placeholder="搜索患者姓名/ID..." 
              className="pl-9 pr-4 py-2 bg-white border border-slate-200 rounded-3xl text-sm focus:ring-2 focus:ring-brand outline-none w-64"
            />
          </div>
          <button className="p-2 bg-white border border-slate-200 rounded-3xl hover:bg-slate-50">
            <Filter className="w-4 h-4 text-slate-600" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 flex-1">
        {/* Left Column: Ward Overview & Alerts */}
        <div className="xl:col-span-1 space-y-6">
          {/* Ward Stats */}
          <div className="bg-white/60 backdrop-blur-xl rounded-3xl border border-white/80 p-6 grid grid-cols-2 gap-4 shadow-sm">
            <div className="space-y-1">
              <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">在院人数</div>
              <div className="text-2xl font-bold text-slate-900">32</div>
            </div>
            <div className="space-y-1">
              <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">待办任务</div>
              <div className="text-2xl font-bold text-brand">12</div>
            </div>
            <div className="space-y-1">
              <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">一级护理</div>
              <div className="text-2xl font-bold text-orange-500">5</div>
            </div>
            <div className="space-y-1">
              <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">病危/重</div>
              <div className="text-2xl font-bold text-red-500">2</div>
            </div>
          </div>

          {/* Vital Alerts */}
          <div className="bg-white/60 backdrop-blur-xl rounded-3xl border border-white/80 p-6 space-y-4 shadow-sm">
            <h3 className="font-bold text-slate-900 flex items-center">
              <Zap className="w-5 h-5 mr-2 text-orange-500" />
              体征预警
            </h3>
            <div className="space-y-3">
              {VITAL_ALERTS.map((alert, i) => (
                <div key={i} className="p-3 rounded-2xl bg-orange-50 border border-orange-100 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-900">{alert.patient} ({alert.bed}床)</span>
                    <span className="text-[10px] text-orange-600 font-bold">{alert.level}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center text-xs text-slate-600">
                      {alert.type === '心率' ? <Heart className="w-3 h-3 mr-1 text-red-500" /> : <Thermometer className="w-3 h-3 mr-1 text-orange-500" />}
                      {alert.type}: <span className="font-bold ml-1">{alert.value}</span>
                    </div>
                    <span className="text-[10px] text-slate-400">{alert.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Middle Column: Task List & Schedule */}
        <div className="xl:col-span-2 bg-white/60 backdrop-blur-xl rounded-3xl border border-white/80 p-6 flex flex-col shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-bold text-slate-900 flex items-center text-lg">
              <Clock className="w-6 h-6 mr-2 text-brand" />
              护理任务清单
            </h3>
            <div className="flex items-center space-x-2">
              <button className="px-3 py-1.5 bg-brand text-white text-xs font-bold rounded-lg shadow-lg shadow-brand/20">
                扫码执行
              </button>
            </div>
          </div>

          <div className="space-y-4 overflow-y-auto pr-2">
            {WARD_TASKS.map((task) => (
              <motion.div 
                key={task.id}
                whileHover={{ x: 4 }}
                className="p-4 rounded-2xl border border-slate-100 hover:border-brand/30 hover:bg-brand/5 transition-all flex items-center justify-between group"
              >
                <div className="flex items-center space-x-4">
                  <div className={`w-12 h-12 rounded-xl flex flex-col items-center justify-center font-bold ${
                    task.priority === '高' ? 'bg-red-50 text-red-600' : 'bg-slate-50 text-slate-600'
                  }`}>
                    <span className="text-[10px] opacity-60">床位</span>
                    <span className="text-lg leading-tight">{task.bed}</span>
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-slate-900">{task.patient}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        task.priority === '高' ? 'bg-red-100 text-red-600' : 'bg-slate-100 text-slate-500'
                      }`}>
                        {task.priority}优先级
                      </span>
                    </div>
                    <div className="text-sm text-slate-600 mt-1">{task.task}</div>
                  </div>
                </div>
                <div className="text-right space-y-1">
                  <div className="text-sm font-bold text-slate-900">{task.time}</div>
                  <div className={`text-[10px] font-bold ${
                    task.status === '进行中' ? 'text-brand' : 'text-slate-400'
                  }`}>{task.status}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Right Column: AI Assistant & Resources */}
        <div className="xl:col-span-1 space-y-6">
          {/* AI Nursing Assistant */}
          <div className="bg-brand rounded-3xl p-6 text-white space-y-4 shadow-xl shadow-brand/20">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-white/20 rounded-xl">
                <Droplets className="w-5 h-5" />
              </div>
              <h3 className="font-bold">AI 护理助手</h3>
            </div>
            <p className="text-xs text-white/80 leading-relaxed">
              "01床张晓彤的输液余量约为15%，预计15分钟后结束，请及时关注。"
            </p>
            <div className="pt-2">
              <button className="w-full py-2 bg-white/20 hover:bg-white/30 rounded-xl text-xs font-bold transition-colors">
                查看详情
              </button>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-white/60 backdrop-blur-xl rounded-3xl border border-white/80 p-6 space-y-4 shadow-sm">
            <h3 className="font-bold text-slate-900">快捷操作</h3>
            <div className="grid grid-cols-2 gap-3">
              {[
                { icon: CheckCircle2, label: '交接班', color: 'text-blue-500' },
                { icon: Thermometer, label: '批量体温', color: 'text-orange-500' },
                { icon: Droplets, label: '输液巡视', color: 'text-brand' },
                { icon: User, label: '宣教推送', color: 'text-purple-500' },
              ].map((action, i) => (
                <button key={i} className="flex flex-col items-center justify-center p-3 rounded-2xl border border-slate-100 hover:bg-slate-50 transition-colors space-y-2">
                  <action.icon className={`w-5 h-5 ${action.color}`} />
                  <span className="text-[10px] font-bold text-slate-600">{action.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
