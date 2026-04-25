// AI 辅助诊断视图：用于展示诊断分析相关的静态演示内容。
import React, { useState } from 'react';
import { 
  User, Activity, AlertCircle, CheckCircle2, 
  Mic, Pause, Play, Send, Sparkles, 
  FileText, ClipboardList, Stethoscope, Beaker, 
  ChevronRight, Info, Search, Database, 
  Clock, Heart, ShieldAlert, Zap, Brain,
  ArrowRight, Share2, Download
} from 'lucide-react';
import { motion } from 'motion/react';

/**
 * AI 辅助诊断视图组件：
 * 提供一个静态的演示页面，包含信息采集（语音输入）、AI 结构化病历生成、
 * 以及 AI 辅助预分析（预警、缺失提醒等）的流程展示。
 */
export function AIDiagnosisView() {
  const [activeStep, setActiveStep] = useState(1);
  const [activeTab, setActiveTab] = useState('主诉');
  const [isRecording, setIsRecording] = useState(true);

  const steps = [
    { id: 1, label: '信息采集' },
    { id: 2, label: 'AI诊断' },
    { id: 3, label: '诊断确认' },
    { id: 4, label: '方案流转' },
  ];

  const tabs = ['主诉', '现病史', '既往史', '体格检查', '辅助检查'];
  const dataSources = [
    { id: 'his', label: 'HIS 患者信息', status: '已同步', color: 'text-green-500' },
    { id: 'lis', label: 'LIS 检验报告', status: '3份报告', color: 'text-green-500' },
    { id: 'pacs', label: 'PACS 影像', status: '加载中...', color: 'text-brand' },
    { id: 'exam', label: '体检系统', status: '2次体检', color: 'text-green-500' },
  ] as const;
  const extractedItems = [
    { id: 'symptom', label: '症状', value: '口渴多饮 · 多尿 · 体重下降 · 乏力', color: 'bg-blue-50 text-blue-600' },
    { id: 'duration', label: '时间', value: '3个月', color: 'bg-orange-50 text-orange-600' },
    { id: 'family', label: '家族', value: '父亲: 2型糖尿病', color: 'bg-pink-50 text-pink-600' },
  ] as const;
  const completenessItems = [
    { id: 'chief', label: '主诉信息', status: '完整', color: 'text-green-500' },
    { id: 'present', label: '现病史', status: '完整', color: 'text-green-500' },
    { id: 'physical', label: '体格检查', status: '待录入', color: 'text-slate-400' },
    { id: 'report', label: '检验报告', status: '3份', color: 'text-green-500' },
    { id: 'image', label: '影像报告', status: '加载中', color: 'text-brand' },
  ] as const;

  return (
    <div className="flex flex-col h-full">
      {/* Stepper / Sub-header */}
      <div className="bg-white/60 backdrop-blur-xl border-b border-white/80 px-8 py-4 flex items-center justify-center shrink-0 shadow-sm">
        <div className="flex items-center space-x-12">
          {steps.map((step) => (
            <div key={step.id} className="flex items-center space-x-3">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all ${
                activeStep === step.id 
                  ? 'bg-brand text-white shadow-lg shadow-brand/30 ring-4 ring-brand/10' 
                  : activeStep > step.id 
                    ? 'bg-brand/10 text-brand' 
                    : 'bg-slate-100 text-slate-400'
              }`}>
                {activeStep > step.id ? <CheckCircle2 className="w-5 h-5" /> : step.id}
              </div>
              <span className={`text-sm font-medium ${
                activeStep === step.id ? 'text-slate-900' : 'text-slate-400'
              }`}>{step.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden p-6 gap-6">
        {/* Left Sidebar: Patient Info */}
        <aside className="w-80 flex flex-col gap-6 overflow-y-auto custom-scrollbar shrink-0">
          {/* Patient Card */}
          <div className="bg-white/60 backdrop-blur-xl rounded-3xl p-6 shadow-sm border border-white/80">
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center space-x-4">
                <div className="w-14 h-14 rounded-2xl bg-brand-light/30 flex items-center justify-center text-brand">
                  <User className="w-8 h-8" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-slate-900">张丽华</h2>
                  <p className="text-sm text-slate-500">女 · 45岁 · 初诊</p>
                </div>
              </div>
              <button className="p-2 text-slate-400 hover:text-brand transition-colors">
                <Info className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between text-sm">
                <span className="text-slate-400">病历号</span>
                <span className="font-mono font-medium text-slate-900">MR-2026-04521</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-400">预约科目</span>
                <span className="font-medium text-slate-900">内分泌科</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-400">就诊时间</span>
                <span className="font-medium text-slate-900">2026-03-20 09:30</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-400">家族史</span>
                <span className="font-medium text-slate-900">父: 2型糖尿病</span>
              </div>
            </div>
          </div>

          {/* Allergy Alert */}
          <div className="bg-red-50/80 backdrop-blur-xl rounded-3xl p-6 border border-red-100 shadow-sm">
            <div className="flex items-center space-x-2 text-red-600 mb-3">
              <ShieldAlert className="w-5 h-5" />
              <h3 className="font-bold">过敏史警示</h3>
            </div>
            <p className="text-sm text-red-700 font-medium leading-relaxed">
              青霉素类 — 严重过敏（皮疹+呼吸困难）
            </p>
          </div>

          {/* Data Sources */}
          <div className="bg-white/60 backdrop-blur-xl rounded-3xl p-6 shadow-sm border border-white/80">
            <div className="flex items-center space-x-2 mb-6">
              <Database className="w-5 h-5 text-slate-400" />
              <h3 className="font-bold text-slate-900">数据源接入状态</h3>
            </div>
            <div className="space-y-5">
              {dataSources.map((source) => (
                <div key={source.id} className="flex items-center justify-between text-sm">
                  <div className="flex items-center space-x-3">
                    <div className={`w-2 h-2 rounded-full ${source.color.replace('text', 'bg')}`}></div>
                    <span className="text-slate-600">{source.label}</span>
                  </div>
                  <span className={`font-medium ${source.color}`}>{source.status}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col gap-6 overflow-hidden">
          {/* Voice Consultation */}
          <section className="bg-white/60 backdrop-blur-xl rounded-3xl p-8 shadow-sm border border-white/80 flex flex-col shrink-0">
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center space-x-3">
                <Mic className="w-6 h-6 text-brand" />
                <h3 className="text-lg font-bold text-slate-900">语音问诊采集</h3>
              </div>
              {isRecording && (
                <div className="flex items-center space-x-2 px-3 py-1.5 bg-red-50 text-red-600 rounded-full text-xs font-bold animate-pulse">
                  <div className="w-2 h-2 rounded-full bg-red-600"></div>
                  <span>录音中 00:42</span>
                </div>
              )}
            </div>

            <div className="bg-slate-50 rounded-2xl p-8 mb-6 flex flex-col items-center justify-center min-h-[120px] relative overflow-hidden">
              {/* Waveform Visualization */}
              <div className="flex items-center space-x-1 h-12">
                {[...Array(24)].map((_, i) => (
                  <motion.div
                    key={`wave-${i}`}
                    animate={{ 
                      height: isRecording ? [10, Math.random() * 40 + 10, 10] : 4 
                    }}
                    transition={{ 
                      repeat: Infinity, 
                      duration: 0.5 + Math.random() * 0.5,
                      ease: "easeInOut"
                    }}
                    className="w-1 bg-brand rounded-full"
                  />
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center space-x-2 text-slate-400">
                <span className="text-xs font-bold uppercase tracking-wider">实时转写</span>
              </div>
              <p className="text-slate-700 leading-relaxed">
                患者张丽华，女性，45岁，主诉口渴多饮多尿3个月，伴体重下降约5公斤。近期感觉乏力明显，视物模糊。既往体健，否认高血压史。家族史：父亲有2型糖尿病病史...
              </p>
            </div>

            <div className="flex items-center justify-end space-x-4 mt-8">
              <button 
                onClick={() => setIsRecording(!isRecording)}
                className="flex items-center space-x-2 px-6 py-3 bg-slate-100 text-slate-600 rounded-2xl font-bold hover:bg-slate-200 transition-all"
              >
                {isRecording ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
                <span>{isRecording ? '暂停' : '继续'}</span>
              </button>
              <button className="flex items-center space-x-2 px-8 py-3 bg-brand text-white rounded-2xl font-bold hover:bg-brand-hover transition-all shadow-lg shadow-brand/20">
                <CheckCircle2 className="w-5 h-5" />
                <span>完成采集</span>
              </button>
            </div>
          </section>

          {/* Structured Medical Record */}
          <section className="bg-white/60 backdrop-blur-xl rounded-3xl p-8 shadow-sm border border-white/80 flex-1 flex flex-col overflow-hidden">
            <div className="flex items-center justify-between mb-8 shrink-0">
              <div className="flex items-center space-x-3">
                <FileText className="w-6 h-6 text-brand" />
                <h3 className="text-lg font-bold text-slate-900">AI结构化病历（实时生成中）</h3>
              </div>
              <button className="flex items-center space-x-2 px-4 py-2 bg-brand-light/20 text-brand rounded-xl text-sm font-bold hover:bg-brand-light/30 transition-all">
                <Zap className="w-4 h-4" />
                <span>AI生成</span>
              </button>
            </div>

            <div className="flex items-center space-x-2 mb-8 border-b border-slate-100 shrink-0">
              {tabs.map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-6 py-3 text-sm font-bold transition-all relative ${
                    activeTab === tab ? 'text-brand' : 'text-slate-400 hover:text-slate-600'
                  }`}
                >
                  {tab}
                  {activeTab === tab && (
                    <motion.div layoutId="activeTab" className="absolute bottom-0 left-0 right-0 h-1 bg-brand rounded-full" />
                  )}
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar">
              <div className="bg-slate-50 rounded-2xl p-6 min-h-[100px]">
                <p className="text-slate-900 font-medium text-lg">口渴多饮、多尿3个月，体重下降5kg</p>
              </div>
            </div>

            <div className="flex items-center space-x-6 mt-8 shrink-0">
              <div className="flex items-center space-x-2 text-green-600">
                <CheckCircle2 className="w-4 h-4" />
                <span className="text-sm font-bold">主诉完整</span>
              </div>
              <div className="flex items-center space-x-2 text-green-600">
                <CheckCircle2 className="w-4 h-4" />
                <span className="text-sm font-bold">时间明确</span>
              </div>
              <div className="flex items-center space-x-2 text-orange-500">
                <AlertCircle className="w-4 h-4" />
                <span className="text-sm font-bold">建议补充：发病诱因</span>
              </div>
            </div>
          </section>
        </main>

        {/* Right Sidebar: AI Analysis */}
        <aside className="w-96 flex flex-col gap-6 overflow-y-auto custom-scrollbar shrink-0">
          {/* AI Preliminary Analysis */}
          <div className="bg-white/60 backdrop-blur-xl rounded-3xl p-8 shadow-sm border border-white/80">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center space-x-3">
                <Sparkles className="w-6 h-6 text-brand" />
                <h3 className="text-lg font-bold text-slate-900">AI预分析</h3>
              </div>
              <span className="px-2 py-1 bg-brand-light/20 text-brand rounded text-[10px] font-bold">分析中</span>
            </div>
            <p className="text-sm text-slate-500 leading-relaxed mb-8">
              基于WiNGPT医疗模型，AI正在实时分析语音转写内容，提取关键症状特征...
            </p>

            <div className="space-y-6">
              <div className="text-sm font-bold text-slate-400 mb-3">已提取关键信息</div>
              <div className="space-y-4">
                {extractedItems.map((item) => (
                  <div key={item.id} className="flex items-start space-x-4">
                    <span className={`px-2 py-1 rounded text-xs font-bold shrink-0 ${item.color}`}>{item.label}</span>
                    <span className="text-sm text-slate-700 font-medium">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Data Completeness */}
          <div className="bg-white/60 backdrop-blur-xl rounded-3xl p-8 shadow-sm border border-white/80">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-slate-900">数据完整度</h3>
              <span className="text-brand font-bold text-xl">68%</span>
            </div>
            
            <div className="w-full h-2 bg-slate-100 rounded-full mb-8 overflow-hidden">
              <motion.div 
                initial={{ width: 0 }}
                animate={{ width: '68%' }}
                className="h-full bg-brand rounded-full"
              />
            </div>

            <div className="space-y-4">
              {completenessItems.map((item) => (
                <div key={item.id} className="flex items-center justify-between text-sm">
                  <div className="flex items-center space-x-3">
                    <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                      item.status === '完整' ? 'bg-green-500 border-green-500 text-white' : 'border-slate-200'
                    }`}>
                      {item.status === '完整' && <CheckCircle2 className="w-3 h-3" />}
                    </div>
                    <span className="text-slate-600">{item.label}</span>
                  </div>
                  <span className={`font-bold ${item.color}`}>{item.status}</span>
                </div>
              ))}
            </div>
          </div>

          {/* AI Initial Findings */}
          <div className="bg-white/60 backdrop-blur-xl rounded-3xl p-8 shadow-sm border border-white/80 space-y-6">
            <div className="flex items-center space-x-3">
              <Zap className="w-6 h-6 text-brand" />
              <h3 className="text-lg font-bold text-slate-900">AI初步发现</h3>
            </div>

            <div className="space-y-4">
              <div className="bg-orange-50 rounded-2xl p-4 border border-orange-100">
                <div className="text-orange-600 font-bold text-sm mb-2">疑似代谢异常</div>
                <p className="text-xs text-orange-700 leading-relaxed">
                  三多一少症状 + 家族史阳性，高度提示糖尿病可能
                </p>
              </div>

              <div className="bg-blue-50 rounded-2xl p-4 border border-blue-100">
                <div className="text-blue-600 font-bold text-sm mb-2">建议优先检查</div>
                <p className="text-xs text-blue-700 leading-relaxed">
                  FPG · HbA1c · OGTT · 胰岛功能 · 糖尿病自身抗体
                </p>
              </div>

              <div className="bg-red-50 rounded-2xl p-4 border border-red-100">
                <div className="text-red-600 font-bold text-sm mb-2">用药注意</div>
                <p className="text-xs text-red-700 leading-relaxed">
                  患者青霉素过敏，需避免相关药物交叉反应
                </p>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
