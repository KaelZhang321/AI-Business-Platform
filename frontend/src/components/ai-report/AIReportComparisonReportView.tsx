import React, { useRef, useState, useEffect } from 'react';
import { aiReportApi } from '../../services/api/aiReportApi';
import { motion } from 'motion/react';
import { GoogleGenAI, Type } from '@google/genai';
import type { CardSwapRef } from './CardSwap';
import { ArchivesPanel } from './reportview/ArchivesPanel';
import { ComparisonModal } from './reportview/ComparisonModal';
import { CustomerInfoPanel } from './reportview/CustomerInfoPanel';
import { CARD_STACK_YEARS, DEFAULT_MESSAGES, METRICS } from './reportview/data';
import { ReportHeader } from './reportview/ReportHeader';
import type { AIReportComparisonReportViewProps, Message } from './reportview/types';

const ai = new GoogleGenAI({ apiKey: import.meta.env.VITE_GEMINI_API_KEY ?? '' });

export const AIReportComparisonReportView: React.FC<AIReportComparisonReportViewProps> = ({
  customer,
  onBack,
  isDarkMode,
  setIsDarkMode,
}) => {
  const cardSwapRef = useRef<CardSwapRef>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<Message[]>(DEFAULT_MESSAGES);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [focusedMetricName, setFocusedMetricName] = useState<string | null>(null);
  const [selectedYearForModal, setSelectedYearForModal] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'trend'>('list');
  const [modalFilter, setModalFilter] = useState<'all' | 'abnormal'>('all');
  const [modalViewMode, setModalViewMode] = useState<'card' | 'list'>('card');

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 获取体检报告
  useEffect(() => {
    aiReportApi.getPatientExamListApi({ idCard: 'iKTqBmD8Ej7krRCUFy7u5yrjPhQFrq9xe/CCzNn+GHQ=' }).then((res) => {
      console.log('getPatientExamListApi response:', res);
      // 转换数据

    }).catch(console.error);
  }, []);

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) {
      e.preventDefault();
    }

    if (!inputValue.trim() || isTyping) {
      return;
    }

    const userMsg = inputValue.trim();
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }]);
    setInputValue('');
    setIsTyping(true);

    try {
      const response = await ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: userMsg,
        config: {
          systemInstruction: `你是一个专业的健康体检报告分析助手。
          当前可查询的指标有：${METRICS.map((m) => m.name).join(', ')}。

          你的任务是：
          1. 分析用户的意图，判断用户是否在询问某个具体的体检指标。
          2. 如果是，请在回复中包含该指标的完整名称。
          3. 必须以 JSON 格式返回，包含两个字段：
             - "reply": 你对用户的自然语言回复，解释该指标的意义或现状。
             - "focusedMetric": 识别到的指标名称（必须是上述列表中的一个，如果没识别到则为 null）。

          示例：
          用户：“帮我看看血糖怎么样”
          返回：{"reply": "好的，正在为您调取历年的空腹血糖数据。从趋势看，您的血糖近年来有持续上升的迹象，建议重点关注。", "focusedMetric": "空腹血糖"}`,
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              reply: { type: Type.STRING },
              focusedMetric: { type: Type.STRING, nullable: true },
            },
            required: ['reply', 'focusedMetric'],
          },
        },
      });

      const result = JSON.parse(response.text || '{}');
      setMessages((prev) => [...prev, { role: 'ai', content: result.reply }]);
      if (result.focusedMetric) {
        setFocusedMetricName(result.focusedMetric);
      }
    } catch (error) {
      console.error('AI Chat Error:', error);
      setMessages((prev) => [...prev, { role: 'ai', content: '抱歉，我刚才走神了，请再试一次。' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleSwapCard = () => {
    cardSwapRef.current?.swap();
  };

  const handleResetView = () => {
    setFocusedMetricName(null);
    setMessages([{ role: 'ai', content: '已为您重置视图。您可以继续询问关于体检指标的问题。' }]);
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="h-full flex flex-col space-y-6 p-6 bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-white via-slate-50 to-slate-100 dark:bg-none dark:bg-slate-900 transition-colors duration-300 overflow-hidden"
    >
      <ReportHeader
        onBack={onBack}
        isDarkMode={isDarkMode}
        onToggleDarkMode={() => setIsDarkMode(!isDarkMode)}
        onResetView={handleResetView}
      />

      <div className="flex-1 flex flex-col lg:flex-row gap-6 min-h-0 overflow-hidden">
        <CustomerInfoPanel
          customer={customer}
          messages={messages}
          inputValue={inputValue}
          isTyping={isTyping}
          focusedMetricName={focusedMetricName}
          chatEndRef={chatEndRef}
          onInputChange={setInputValue}
          onSubmit={handleSendMessage}
          onResetFocus={() => setFocusedMetricName(null)}
        />

        <ArchivesPanel
          focusedMetricName={focusedMetricName}
          metrics={METRICS}
          cardStack={CARD_STACK_YEARS}
          cardSwapRef={cardSwapRef}
          viewMode={viewMode}
          onChangeViewMode={setViewMode}
          onOpenModal={setSelectedYearForModal}
          onSwapCard={handleSwapCard}
          onFocusMetric={setFocusedMetricName}
        />
      </div>

      <ComparisonModal
        selectedYearForModal={selectedYearForModal}
        metrics={METRICS}
        modalFilter={modalFilter}
        modalViewMode={modalViewMode}
        onModalFilterChange={setModalFilter}
        onModalViewModeChange={setModalViewMode}
        onSelectYear={setSelectedYearForModal}
        onClose={() => setSelectedYearForModal(null)}
      />
    </motion.div>
  );
};
