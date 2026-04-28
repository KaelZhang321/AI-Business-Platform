import React, { useState, useRef } from 'react';
import { Activity, Zap } from 'lucide-react';
import { motion } from 'motion/react';
import type { CustomerRecord } from './types';

interface ReflectiveCardProps {
  customer: CustomerRecord;
  onViewDetails: (customer: CustomerRecord) => void;
}

export const ReflectiveCard: React.FC<ReflectiveCardProps> = ({ customer, onViewDetails }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);
  const [rotation, setRotation] = useState({ x: 0, y: 0 });
  const teacherText = [customer.mainTeacherName, customer.subTeacherName].filter(Boolean).join(' / ');
  const summaryParts = [customer.typeName, customer.storeName].filter(Boolean);
  if (teacherText) {
    summaryParts.push(`带教: ${teacherText}`);
  }
  const summaryText = summaryParts.length > 0 ? summaryParts.join(' · ') : customer.keyAbnormal;

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setMousePos({ x, y });

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const rotateX = (y - centerY) / 20;
    const rotateY = (centerX - x) / 20;
    setRotation({ x: rotateX, y: rotateY });
  };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setRotation({ x: 0, y: 0 });
      }}
      onClick={() => onViewDetails(customer)}
      style={{
        perspective: 1000,
        transformStyle: 'preserve-3d',
        transform: isHovered ? `rotateX(${rotation.x}deg) rotateY(${rotation.y}deg)` : 'rotateX(0deg) rotateY(0deg)',
        transition: isHovered ? 'none' : 'transform 0.5s cubic-bezier(0.23, 1, 0.32, 1)',
      }}
      className="relative group bg-white dark:bg-slate-800/90 rounded-2xl border border-slate-200/60 dark:border-slate-700/60 p-6 shadow-sm overflow-hidden cursor-pointer hover:shadow-xl flex flex-col min-h-[260px] h-full"
    >
      <div
        className="pointer-events-none absolute -inset-px opacity-0 group-hover:opacity-100 transition-opacity duration-500 z-0"
        style={{
          background: `radial-gradient(500px circle at ${mousePos.x}px ${mousePos.y}px, rgba(59, 130, 246, 0.08), transparent 50%)`,
        }}
      />

      <div
        className="pointer-events-none absolute -inset-px rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 z-10"
        style={{
          maskImage: 'linear-gradient(black, black), linear-gradient(black, black)',
          maskClip: 'content-box, border-box',
          maskComposite: 'exclude',
          WebkitMaskComposite: 'xor',
          padding: '2px',
        }}
      >
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[200%] h-[200%]"
          style={{
            background:
              'conic-gradient(from 0deg, transparent 50%, rgba(59, 130, 246, 0.2) 70%, rgba(59, 130, 246, 0.8) 90%, rgba(59, 130, 246, 1) 100%)',
          }}
        />
      </div>

      <div
        className="pointer-events-none absolute -inset-px rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 z-20"
        style={{
          background: `radial-gradient(300px circle at ${mousePos.x}px ${mousePos.y}px, rgba(59, 130, 246, 0.4), transparent 60%)`,
          maskImage: 'linear-gradient(black, black), linear-gradient(black, black)',
          maskClip: 'content-box, border-box',
          maskComposite: 'exclude',
          WebkitMaskComposite: 'xor',
          padding: '1px',
        }}
      />

      <div className="relative z-10 flex flex-col h-full" style={{ transform: 'translateZ(30px)' }}>
        <div className="flex justify-between items-start mb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center text-slate-600 dark:text-slate-300 font-bold text-lg shadow-inner">
              {(customer.name || '客').charAt(0)}
            </div>
            <div>
              <h4 className="text-lg font-bold text-slate-900 dark:text-white group-hover:text-brand transition-colors">{customer.name}</h4>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {customer.gender} · {customer.age}岁
              </p>
            </div>
          </div>
          <span
            className={`px-2.5 py-1 rounded-lg text-[10px] font-bold shadow-sm ${
              customer.aiJudgment === '重点关注'
                ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/20 dark:text-rose-400'
                : customer.aiJudgment === '持续观察'
                  ? 'bg-amber-50 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400'
                  : customer.aiJudgment === '优先复查'
                    ? 'bg-blue-50 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400'
                    : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400'
            }`}
          >
            {customer.aiJudgment}
          </span>
        </div>

        <div className="flex-1 py-4 border-y border-slate-100 dark:border-slate-700/50 my-2 flex flex-col justify-center">
          <div className="flex items-center text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-2">
            <Activity className="w-3 h-3 mr-1 text-brand" />
            客户摘要
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-300 line-clamp-3 leading-relaxed">{summaryText}</p>
        </div>

        <div className="pt-2 flex items-center justify-between mt-auto">
          <div className="text-[10px] text-slate-400 font-medium">最近体检: {customer.lastCheckDate}</div>
          <div className="text-xs font-bold text-brand flex items-center group-hover:translate-x-1 transition-transform">
            查看详情 <Zap className="w-3 h-3 ml-1 fill-current" />
          </div>
        </div>
      </div>
    </div>
  );
};
