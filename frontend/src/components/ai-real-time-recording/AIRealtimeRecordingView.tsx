import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ChevronLeft, Mic, Square, Play, Pause, FileText, Activity, HeartPulse, Stethoscope, Save, CheckCircle2, AlertCircle, Sparkles, Paperclip } from 'lucide-react';
import { BorderBeam } from 'border-beam';

const CUSTOMERS = [
  { id: 'c1', name: '张女士', gender: '女', age: 45 },
  { id: 'c2', name: '李先生', gender: '男', age: 52 },
  { id: 'c3', name: '王阿姨', gender: '女', age: 60 }
];

interface AIRealtimeRecordingViewProps {
  setCurrentPage: (page: any) => void;
  isDarkMode: boolean;
  setIsDarkMode: (value: boolean) => void;
  hideHeader?: boolean;
}

export const AIRealtimeRecordingView: React.FC<AIRealtimeRecordingViewProps> = ({ setCurrentPage, isDarkMode, setIsDarkMode, hideHeader = false }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [transcription, setTranscription] = useState<{speaker: 'doctor' | 'client', text: string, time: string}[]>([]);
  const [summary, setSummary] = useState<{
    keyPoints: string[];
    physicalCondition: string[];
    suggestions: string[];
  } | null>(null);
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [selectedSummaryTab, setSelectedSummaryTab] = useState<'all' | 'keyPoints' | 'physicalCondition' | 'suggestions'>('all');
  
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // Mock conversation script
  const mockScript = [
    { speaker: 'doctor', text: '张女士您好，最近感觉身体怎么样？上次体检后有按时吃药吗？', delay: 2000 },
    { speaker: 'client', text: '医生您好，药有按时吃。就是最近感觉容易疲劳，晚上睡眠也不太好，经常半夜醒来。', delay: 5000 },
    { speaker: 'doctor', text: '睡眠不好大概有多久了？有没有伴随心慌或者出汗的情况？', delay: 8000 },
    { speaker: 'client', text: '大概有一两周了。偶尔会觉得心跳有点快，出汗倒是不明显。另外就是感觉胃口也没有以前好了。', delay: 12000 },
    { speaker: 'doctor', text: '好的，我记录一下。您的空腹血糖之前偏高，最近饮食有控制吗？', delay: 16000 },
    { speaker: 'client', text: '有注意控制甜食，但主食吃得还是比较多。', delay: 19000 },
  ];

  useEffect(() => {
    if (isRecording && !isPaused) {
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRecording, isPaused]);

  useEffect(() => {
    if (isRecording && !isPaused) {
      // Simulate real-time transcription
      const timeouts: NodeJS.Timeout[] = [];
      mockScript.forEach((item) => {
        if (recordingTime === Math.floor(item.delay / 1000)) {
          setTranscription(prev => [...prev, {
            speaker: item.speaker as 'doctor' | 'client',
            text: item.text,
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }]);
        }
      });
      return () => timeouts.forEach(clearTimeout);
    }
  }, [recordingTime, isRecording, isPaused]);

  useEffect(() => {
    // Auto scroll to bottom of transcript
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcription]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleStartRecording = () => {
    setIsRecording(true);
    setIsPaused(false);
    setTranscription([]);
    setSummary(null);
    setRecordingTime(0);
  };

  const handleStopRecording = () => {
    setIsRecording(false);
    setIsPaused(false);
    setIsGeneratingSummary(true);
    
    // Simulate AI generating summary
    setTimeout(() => {
      setSummary({
        keyPoints: [
          '患者主诉近期易疲劳，睡眠质量差（易醒）',
          '伴有偶发性心悸（心跳快）',
          '食欲近期有所下降',
          '饮食控制方面：已限制甜食，但碳水（主食）摄入仍偏高'
        ],
        physicalCondition: [
          '空腹血糖偏高病史',
          '疑似存在植物神经功能紊乱或轻度焦虑（睡眠差、心悸）',
          '需关注心血管及内分泌代谢状况'
        ],
        suggestions: [
          '建议进行动态心电图（Holter）检查，排查心悸原因',
          '复查空腹及餐后2小时血糖、糖化血红蛋白',
          '调整饮食结构：减少精细主食比例，增加粗粮和膳食纤维',
          '可考虑开具改善睡眠的温和中成药或进行心理疏导'
        ]
      });
      setIsGeneratingSummary(false);
    }, 2500);
  };

  const handlePauseRecording = () => {
    setIsPaused(!isPaused);
  };

  return (
    <div className="space-y-6 pb-12 h-full flex flex-col relative">
      {/* Header */}
      {!hideHeader && (
        <div className="flex items-center justify-between px-8 pt-4 shrink-0">
          <div className="flex items-center space-x-4">
            <button 
              onClick={() => setCurrentPage('function-square')}
              className="p-2 bg-white dark:bg-slate-800 rounded-xl shadow-sm hover:shadow-md transition-all text-slate-500 dark:text-slate-400 hover:text-brand dark:hover:text-brand-400"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <div>
              <div className="flex items-center space-x-3">
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">AI实时录制与分析</h1>
                <span className="px-2 py-1 bg-brand/10 text-brand text-xs font-bold rounded-lg">Beta</span>
              </div>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">实时记录医患沟通，智能提取关键信息，辅助制定个性化方案。</p>
            </div>
          </div>
        </div>
      )}

      <div className="flex-1 px-8 grid grid-cols-12 gap-6 min-h-0">
        {/* Left Column: Recording & Transcript */}
        <div className="col-span-12 lg:col-span-7 flex flex-col space-y-6 min-h-0">
          
          {/* Client Selection & Controls */}
          <div className="bg-white dark:bg-slate-800 rounded-3xl p-6 shadow-sm border border-slate-200 dark:border-slate-700 shrink-0">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center space-x-4">
                <select 
                  className="bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-brand"
                  value={selectedClientId || ''}
                  onChange={(e) => setSelectedClientId(e.target.value)}
                  disabled={isRecording}
                >
                  <option value="">选择沟通客户...</option>
                  {CUSTOMERS.map(c => (
                    <option key={c.id} value={c.id}>{c.name} ({c.gender}, {c.age}岁)</option>
                  ))}
                </select>
                {selectedClientId && (
                  <span className="text-xs text-slate-500 flex items-center">
                    <CheckCircle2 className="w-3 h-3 text-green-500 mr-1" /> 已就绪
                  </span>
                )}
              </div>
              
              <div className="flex items-center space-x-4">
                <div className="text-2xl font-mono font-bold text-slate-700 dark:text-slate-300 w-24 text-center">
                  {formatTime(recordingTime)}
                </div>
                
                {!isRecording ? (
                  <div className="flex items-center space-x-3">
                    <input 
                      type="file" 
                      id="upload-attachment" 
                      className="hidden" 
                      onChange={(e) => {
                        if (e.target.files && e.target.files.length > 0) {
                          alert(`已选择文件: ${e.target.files[0].name}`);
                        }
                      }}
                    />
                    <label 
                      htmlFor="upload-attachment"
                      className="flex items-center space-x-2 px-4 py-3 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-full font-bold hover:bg-slate-200 dark:hover:bg-slate-600 transition-all cursor-pointer"
                    >
                      <Paperclip className="w-5 h-5" />
                      <span>上传附件</span>
                    </label>
                    
                    <button 
                      onClick={handleStartRecording}
                      disabled={!selectedClientId}
                      className="relative focus:outline-none transition-transform hover:-translate-y-0.5 active:translate-y-0 disabled:transform-none disabled:opacity-50"
                    >
                      <BorderBeam 
                        size="sm" 
                        colorVariant="colorful" 
                        theme={isDarkMode ? 'dark' : 'light'} 
                        active={true}
                        duration={2}
                        className="rounded-full"
                      >
                        <div className="flex items-center space-x-2 px-6 py-3 rounded-full font-bold bg-white dark:bg-slate-900 border border-transparent shadow-lg text-slate-900 dark:text-white">
                          <Mic className="w-5 h-5 text-red-500" />
                          <span>开始录制</span>
                        </div>
                      </BorderBeam>
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center space-x-3">
                    <button 
                      onClick={handlePauseRecording}
                      className="relative focus:outline-none transition-transform hover:-translate-y-0.5 active:translate-y-0"
                    >
                      <BorderBeam 
                        size="sm" 
                        colorVariant="sunset" 
                        theme={isDarkMode ? 'dark' : 'light'} 
                        active={!isPaused}
                        duration={2}
                        className="rounded-full"
                      >
                        <div className="p-3 rounded-full bg-white dark:bg-slate-900 border border-transparent shadow-lg text-slate-900 dark:text-white">
                          {isPaused ? <Play className="w-5 h-5" /> : <Pause className="w-5 h-5 text-orange-500" />}
                        </div>
                      </BorderBeam>
                    </button>
                    
                    <button 
                      onClick={handleStopRecording}
                      className="relative focus:outline-none transition-transform hover:-translate-y-0.5 active:translate-y-0"
                    >
                      <BorderBeam 
                        size="sm" 
                        colorVariant="ocean" 
                        theme={isDarkMode ? 'dark' : 'light'} 
                        active={true}
                        duration={3}
                        className="rounded-full"
                      >
                        <div className="flex items-center space-x-2 px-6 py-3 rounded-full font-bold bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 shadow-lg text-slate-700 dark:text-slate-200">
                          <Square className="w-5 h-5 text-red-500" />
                          <span>结束并分析</span>
                        </div>
                      </BorderBeam>
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Audio Visualizer (Mock) */}
            <div className="h-16 bg-slate-50 dark:bg-slate-900/50 rounded-2xl flex items-center justify-center space-x-1 overflow-hidden px-4">
              {isRecording && !isPaused ? (
                Array.from({ length: 40 }).map((_, i) => (
                  <motion.div
                    key={i}
                    className="w-1.5 bg-brand rounded-full"
                    animate={{ height: ['20%', '80%', '40%', '100%', '30%'] }}
                    transition={{
                      repeat: Infinity,
                      duration: 1 + Math.random(),
                      delay: Math.random() * 0.5,
                      ease: "easeInOut"
                    }}
                  />
                ))
              ) : (
                <div className="text-sm text-slate-400 flex items-center">
                  <Mic className="w-4 h-4 mr-2" />
                  {isRecording && isPaused ? '录音已暂停' : '等待开始录音...'}
                </div>
              )}
            </div>
          </div>

          {/* Real-time Transcript */}
          <div className="flex-1 bg-white dark:bg-slate-800 rounded-3xl p-6 shadow-sm border border-slate-200 dark:border-slate-700 flex flex-col min-h-0">
            <div className="flex items-center justify-between mb-4 shrink-0">
              <h3 className="font-bold text-slate-900 dark:text-white flex items-center">
                <FileText className="w-5 h-5 mr-2 text-brand" />
                实时对话转写
              </h3>
              {isRecording && !isPaused && (
                <span className="flex items-center text-xs text-brand animate-pulse">
                  <div className="w-2 h-2 bg-brand rounded-full mr-2"></div>
                  正在转写...
                </span>
              )}
            </div>
            
            <div className="flex-1 overflow-y-auto custom-scrollbar pr-4 space-y-4">
              {transcription.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-4">
                  <Mic className="w-12 h-12 opacity-20" />
                  <p>对话内容将在此实时显示</p>
                </div>
              ) : (
                transcription.map((item, idx) => (
                  <motion.div 
                    key={idx}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex flex-col ${item.speaker === 'doctor' ? 'items-end' : 'items-start'}`}
                  >
                    <span className="text-[10px] text-slate-400 mb-1 px-2">{item.speaker === 'doctor' ? '医生/咨询师' : '客户'} · {item.time}</span>
                    <div className={`max-w-[80%] p-3 rounded-2xl text-sm leading-relaxed ${
                      item.speaker === 'doctor' 
                        ? 'bg-brand text-white rounded-tr-sm' 
                        : 'bg-slate-100 dark:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-tl-sm'
                    }`}>
                      {item.text}
                    </div>
                  </motion.div>
                ))
              )}
              <div ref={transcriptEndRef} />
            </div>
          </div>
        </div>

        {/* Right Column: AI Summary */}
        <div className="col-span-12 lg:col-span-5 flex flex-col min-h-0">
          <div className="flex-1 bg-gradient-to-b from-slate-50 to-white dark:from-slate-800/50 dark:to-slate-900 rounded-3xl p-6 shadow-sm border border-slate-200 dark:border-slate-700 flex flex-col min-h-0 relative overflow-hidden">
            
            {/* Background Decoration */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-brand/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none"></div>
            
            <div className="flex items-center justify-between mb-6 shrink-0 relative z-10">
              <h3 className="font-bold text-slate-900 dark:text-white flex items-center text-lg">
                <Sparkles className="w-5 h-5 mr-2 text-purple-500" />
                AI 智能总结
              </h3>
              {summary && (
                <div className="flex items-center space-x-3">
                  <select
                    className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-brand"
                    value={selectedSummaryTab}
                    onChange={(e) => setSelectedSummaryTab(e.target.value as any)}
                  >
                    <option value="all">全部内容</option>
                    <option value="keyPoints">沟通重点</option>
                    <option value="physicalCondition">身体近况</option>
                    <option value="suggestions">医疗建议</option>
                  </select>
                  <button className="flex items-center space-x-1 text-xs font-bold text-brand hover:text-brand-600 bg-brand/10 px-3 py-1.5 rounded-lg transition-colors">
                    <Save className="w-3 h-3" />
                    <span>保存至档案</span>
                  </button>
                </div>
              )}
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 relative z-10">
              {isGeneratingSummary ? (
                <div className="h-full flex flex-col items-center justify-center space-y-6">
                  <div className="relative">
                    <div className="w-16 h-16 border-4 border-slate-200 dark:border-slate-700 rounded-full"></div>
                    <div className="w-16 h-16 border-4 border-brand rounded-full border-t-transparent animate-spin absolute inset-0"></div>
                    <Sparkles className="w-6 h-6 text-brand absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-pulse" />
                  </div>
                  <div className="text-center space-y-2">
                    <p className="font-bold text-slate-700 dark:text-slate-300">AI 正在深度分析对话内容...</p>
                    <p className="text-xs text-slate-500">提取关键症状、评估身体近况、生成个性化方案</p>
                  </div>
                </div>
              ) : summary ? (
                <motion.div 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-6"
                >
                  {/* Key Points */}
                  {(selectedSummaryTab === 'all' || selectedSummaryTab === 'keyPoints') && (
                    <div className="bg-white dark:bg-slate-800 rounded-2xl p-5 border border-slate-100 dark:border-slate-700 shadow-sm">
                      <h4 className="flex items-center text-sm font-bold text-slate-900 dark:text-white mb-4">
                        <AlertCircle className="w-4 h-4 mr-2 text-amber-500" />
                        沟通重点提取
                      </h4>
                      <ul className="space-y-3">
                        {summary.keyPoints.map((point, idx) => (
                          <li key={idx} className="flex items-start">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5 mr-2 shrink-0"></span>
                            <span className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{point}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Physical Condition */}
                  {(selectedSummaryTab === 'all' || selectedSummaryTab === 'physicalCondition') && (
                    <div className="bg-white dark:bg-slate-800 rounded-2xl p-5 border border-slate-100 dark:border-slate-700 shadow-sm">
                      <h4 className="flex items-center text-sm font-bold text-slate-900 dark:text-white mb-4">
                        <Activity className="w-4 h-4 mr-2 text-red-500" />
                        身体近况评估
                      </h4>
                      <ul className="space-y-3">
                        {summary.physicalCondition.map((condition, idx) => (
                          <li key={idx} className="flex items-start">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-500 mt-1.5 mr-2 shrink-0"></span>
                            <span className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{condition}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Suggestions */}
                  {(selectedSummaryTab === 'all' || selectedSummaryTab === 'suggestions') && (
                    <div className="bg-brand/5 dark:bg-brand/10 rounded-2xl p-5 border border-brand/20">
                      <h4 className="flex items-center text-sm font-bold text-brand dark:text-brand-400 mb-4">
                        <Stethoscope className="w-4 h-4 mr-2" />
                        医疗与方案建议
                      </h4>
                      <ul className="space-y-3">
                        {summary.suggestions.map((suggestion, idx) => (
                          <li key={idx} className="flex items-start">
                            <CheckCircle2 className="w-4 h-4 text-brand mt-0.5 mr-2 shrink-0" />
                            <span className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed font-medium">{suggestion}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </motion.div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-4">
                  <div className="w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
                    <Sparkles className="w-8 h-8 opacity-50" />
                  </div>
                  <p className="text-sm">录制结束后，AI 将自动生成结构化总结</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
