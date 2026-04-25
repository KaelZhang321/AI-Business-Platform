// 医疗 AI 工作台：展示患者列表、临床洞察和方案规划信息。
import React from 'react';
import { motion } from 'motion/react';
import { 
  Users, 
  Search, 
  Filter, 
  Stethoscope, 
  Brain, 
  ClipboardList, 
  ChevronRight,
  Activity,
  Calendar,
  Clock,
  MessageSquare,
  AlertCircle
} from 'lucide-react';

/** 医疗 AI 工作台模拟患者数据 */
const PATIENTS = [
  { id: '1', name: '张晓彤', age: 28, gender: '女', condition: '高血压待查', risk: '中', lastVisit: '2024-03-20' },
  { id: '2', name: '李建国', age: 54, gender: '男', condition: '糖尿病', risk: '高', lastVisit: '2024-03-22' },
  { id: '3', name: '王芳', age: 42, gender: '女', condition: '甲状腺结节', risk: '低', lastVisit: '2024-03-21' },
  { id: '4', name: '赵强', age: 35, gender: '男', condition: '急性肠胃炎', risk: '中', lastVisit: '2024-03-23' },
];

/**
 * 医疗 AI 工作台视图组件：
 * 主要面向医生群体，展示待诊患者列表、AI 临床洞察（预警/诊疗建议）、方案规划及患者动态监测。
 */
export function MedicalAIWorkbench() {
  return (
    <div className="h-full flex flex-col space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">医疗AI工作台</h2>
          <p className="text-sm text-slate-500">智能辅助诊疗，提升临床决策效率</p>
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

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 flex-1">
        {/* Left Column: Patient List */}
        <div className="xl:col-span-1 bg-white/60 backdrop-blur-xl rounded-3xl border border-white/80 p-6 flex flex-col space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-slate-900 flex items-center">
              <Users className="w-5 h-5 mr-2 text-brand" />
              待诊患者
            </h3>
            <span className="px-2 py-0.5 bg-brand/10 text-brand text-xs rounded-full font-bold">4 人</span>
          </div>
          
          <div className="space-y-3 overflow-y-auto pr-2">
            {PATIENTS.map((patient) => (
              <motion.div 
                key={patient.id}
                whileHover={{ scale: 1.02 }}
                className="p-4 rounded-2xl border border-slate-100 hover:border-brand/30 hover:bg-brand/5 transition-all cursor-pointer group"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-slate-900">{patient.name}</span>
                    <span className="text-xs text-slate-500">{patient.gender} · {patient.age}岁</span>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    patient.risk === '高' ? 'bg-red-100 text-red-600' : 
                    patient.risk === '中' ? 'bg-orange-100 text-orange-600' : 
                    'bg-green-100 text-green-600'
                  }`}>
                    {patient.risk}风险
                  </span>
                </div>
                <div className="text-xs text-slate-600 mb-2 line-clamp-1">诊断：{patient.condition}</div>
                <div className="flex items-center justify-between text-[10px] text-slate-400">
                  <span className="flex items-center">
                    <Clock className="w-3 h-3 mr-1" />
                    上次就诊: {patient.lastVisit}
                  </span>
                  <ChevronRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Middle Column: AI Analysis & Suggestions */}
        <div className="xl:col-span-2 space-y-6">
          {/* AI Insights Card */}
          <div className="bg-gradient-to-br from-brand to-brand-hover rounded-3xl p-6 text-white shadow-xl shadow-brand/20">
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center space-x-3">
                <div className="p-3 bg-white/20 backdrop-blur-md rounded-2xl">
                  <Brain className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-lg font-bold">AI 临床洞察</h3>
                  <p className="text-white/70 text-xs">基于全量病历数据的智能分析</p>
                </div>
              </div>
              <button className="px-4 py-2 bg-white/20 hover:bg-white/30 backdrop-blur-md rounded-xl text-sm font-bold transition-colors">
                生成报告
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/10">
                <div className="flex items-center text-sm font-bold mb-2">
                  <AlertCircle className="w-4 h-4 mr-2 text-orange-300" />
                  异常预警
                </div>
                <p className="text-xs text-white/80 leading-relaxed">
                  患者 张晓彤 近期血压波动较大，建议关注其用药依从性，并考虑调整降压方案。
                </p>
              </div>
              <div className="bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/10">
                <div className="flex items-center text-sm font-bold mb-2">
                  <Stethoscope className="w-4 h-4 mr-2 text-blue-300" />
                  诊疗建议
                </div>
                <p className="text-xs text-white/80 leading-relaxed">
                  针对 李建国 的糖尿病并发症风险，建议增加眼底检查及肾功能专项评估。
                </p>
              </div>
            </div>
          </div>

          {/* Detailed Workbench Content */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Treatment Plan */}
            <div className="bg-white/60 backdrop-blur-xl rounded-3xl border border-white/80 p-6 space-y-4 shadow-sm">
              <h3 className="font-bold text-slate-900 flex items-center">
                <ClipboardList className="w-5 h-5 mr-2 text-brand" />
                方案规划
              </h3>
              <div className="space-y-3">
                {[
                  { title: '高血压分级管理方案', status: '待审核', date: '今日 10:30' },
                  { title: '糖尿病饮食干预计划', status: '已下达', date: '昨日 16:45' },
                  { title: '术后康复评估路径', status: '草稿', date: '2024-03-22' },
                ].map((plan, i) => (
                  <div key={i} className="flex items-center justify-between p-3 rounded-3xl bg-slate-50 border border-slate-100">
                    <div>
                      <div className="text-sm font-bold text-slate-800">{plan.title}</div>
                      <div className="text-[10px] text-slate-400">{plan.date}</div>
                    </div>
                    <span className={`text-[10px] font-bold ${
                      plan.status === '待审核' ? 'text-orange-500' : 
                      plan.status === '已下达' ? 'text-green-500' : 'text-slate-400'
                    }`}>{plan.status}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Activity */}
            <div className="bg-white/60 backdrop-blur-xl rounded-3xl border border-white/80 p-6 space-y-4 shadow-sm">
              <h3 className="font-bold text-slate-900 flex items-center">
                <Activity className="w-5 h-5 mr-2 text-brand" />
                动态监测
              </h3>
              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 rounded-full bg-red-500 mt-1.5 ring-4 ring-red-100"></div>
                  <div>
                    <div className="text-xs font-bold text-slate-800">心率异常提醒</div>
                    <p className="text-[10px] text-slate-500">患者 王芳 静态心率超过 110bpm</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 rounded-full bg-brand mt-1.5 ring-4 ring-brand/10"></div>
                  <div>
                    <div className="text-xs font-bold text-slate-800">检查报告已出</div>
                    <p className="text-[10px] text-slate-500">患者 赵强 的血常规报告已同步</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-2 h-2 rounded-full bg-slate-300 mt-1.5 ring-4 ring-slate-100"></div>
                  <div>
                    <div className="text-xs font-bold text-slate-800">随访提醒</div>
                    <p className="text-[10px] text-slate-500">明日共有 5 位患者需要进行电话随访</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
