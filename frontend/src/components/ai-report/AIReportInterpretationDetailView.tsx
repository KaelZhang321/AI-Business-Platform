import React, { useState, useMemo, useRef, useEffect, ReactElement } from 'react';
import { CUSTOMERS } from '../../data/mockData';
import { Search, Moon, Sun, Users, UserPlus, AlertCircle, Zap, Activity, LayoutGrid, List, ArrowLeft } from 'lucide-react';
import { motion, useInView, AnimatePresence } from 'motion/react';
import { gsap } from 'gsap';
import { AIReportComparisonReportView } from './AIReportComparisonReportView';
import type { AppPage } from '../../navigation';

export const AnimatedList = React.memo(
  ({
    className,
    children,
    delay = 50,
  }: {
    className?: string;
    children: React.ReactNode;
    delay?: number;
  }) => {
    const [index, setIndex] = useState(0);
    const childrenArray = React.Children.toArray(children);

    useEffect(() => {
      setIndex(0);
    }, [childrenArray.length]);

    useEffect(() => {
      if (index < childrenArray.length - 1) {
        const timeout = setTimeout(() => {
          setIndex((prevIndex) => prevIndex + 1);
        }, delay);
        return () => clearTimeout(timeout);
      }
    }, [index, childrenArray.length, delay]);

    const itemsToShow = useMemo(
      () => childrenArray.slice(0, index + 1),
      [index, childrenArray],
    );

    return (
      <div className={className}>
        <AnimatePresence mode="popLayout">
          {itemsToShow.map((item) => {
            const key = (item as ReactElement).key || Math.random().toString();
            return (
              <AnimatedListItem key={key}>
                {item}
              </AnimatedListItem>
            );
          })}
        </AnimatePresence>
      </div>
    );
  },
);

export function AnimatedListItem({ children }: { children: React.ReactNode; key?: React.Key }) {
  const animations = {
    initial: { scale: 0.8, opacity: 0, y: -20 },
    animate: { scale: 1, opacity: 1, y: 0, originY: 0 },
    exit: { scale: 0.8, opacity: 0, y: 20 },
    transition: { type: "spring", stiffness: 350, damping: 40 },
  };

  return (
    <motion.div {...animations} layout className="w-full h-full">
      {children}
    </motion.div>
  );
}

const AnimatedRow: React.FC<{ customer: any; index: number; onViewDetails: (customer: any) => void }> = ({ customer, index, onViewDetails }) => {
  const ref = useRef(null);
  const inView = useInView(ref, { amount: 0.1, once: false });
  
  return (
    <div
      className="grid grid-cols-12 gap-4 items-center border-b border-slate-50 dark:border-slate-800/50 last:border-none hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors py-4 px-2 rounded-lg"
    >
      <div className="col-span-2 font-bold text-slate-800 dark:text-slate-200">{customer.name}</div>
      <div className="col-span-2 text-slate-600 dark:text-slate-400">{customer.gender} / {customer.age}岁</div>
      <div className="col-span-2 text-slate-600 dark:text-slate-400">{customer.lastCheckDate}</div>
      <div className="col-span-2">
        <span className={`px-3 py-1 rounded-full text-xs font-medium ${
          customer.aiJudgment === '重点关注' ? 'bg-rose-50 text-rose-500 dark:bg-rose-500/10 dark:text-rose-400' :
          customer.aiJudgment === '持续观察' ? 'bg-amber-50 text-amber-500 dark:bg-amber-500/10 dark:text-amber-400' :
          customer.aiJudgment === '优先复查' ? 'bg-blue-50 text-blue-500 dark:bg-blue-500/10 dark:text-blue-400' :
          'bg-emerald-50 text-emerald-500 dark:bg-emerald-500/10 dark:text-emerald-400'
        }`}>
          {customer.aiJudgment}
        </span>
      </div>
      <div className="col-span-3 text-slate-600 dark:text-slate-400 truncate">{customer.keyAbnormal}</div>
      <div className="col-span-1 text-center">
        <button 
          onClick={() => onViewDetails(customer)}
          className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700 transition-colors"
        >
          查看详情
        </button>
      </div>
    </div>
  );
};

const ReflectiveCard: React.FC<{ customer: any; index: number; onViewDetails: (customer: any) => void }> = ({ customer, index, onViewDetails }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);
  const [rotation, setRotation] = useState({ x: 0, y: 0 });

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setMousePos({ x, y });

    // Calculate rotation for tilt effect
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
        transformStyle: "preserve-3d",
        transform: isHovered ? `rotateX(${rotation.x}deg) rotateY(${rotation.y}deg)` : 'rotateX(0deg) rotateY(0deg)',
        transition: isHovered ? 'none' : 'transform 0.5s cubic-bezier(0.23, 1, 0.32, 1)'
      }}
      className="relative group bg-white dark:bg-slate-800/90 rounded-2xl border border-slate-200/60 dark:border-slate-700/60 p-6 shadow-sm overflow-hidden cursor-pointer hover:shadow-xl flex flex-col min-h-[260px] h-full"
    >
      {/* Background Spotlight */}
      <div
        className="pointer-events-none absolute -inset-px opacity-0 group-hover:opacity-100 transition-opacity duration-500 z-0"
        style={{
          background: `radial-gradient(500px circle at ${mousePos.x}px ${mousePos.y}px, rgba(59, 130, 246, 0.08), transparent 50%)`,
        }}
      />

      {/* Animated Border Glow */}
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
          transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[200%] h-[200%]"
          style={{
            background: 'conic-gradient(from 0deg, transparent 50%, rgba(59, 130, 246, 0.2) 70%, rgba(59, 130, 246, 0.8) 90%, rgba(59, 130, 246, 1) 100%)',
          }}
        />
      </div>

      {/* Border Spotlight */}
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
      
      <div className="relative z-10 flex flex-col h-full" style={{ transform: "translateZ(30px)" }}>
        <div className="flex justify-between items-start mb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center text-slate-600 dark:text-slate-300 font-bold text-lg shadow-inner">
              {customer.name.charAt(0)}
            </div>
            <div>
              <h4 className="text-lg font-bold text-slate-900 dark:text-white group-hover:text-brand transition-colors">{customer.name}</h4>
              <p className="text-xs text-slate-500 dark:text-slate-400">{customer.gender} · {customer.age}岁</p>
            </div>
          </div>
          <span className={`px-2.5 py-1 rounded-lg text-[10px] font-bold shadow-sm ${
            customer.aiJudgment === '重点关注' ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/20 dark:text-rose-400' :
            customer.aiJudgment === '持续观察' ? 'bg-amber-50 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400' :
            customer.aiJudgment === '优先复查' ? 'bg-blue-50 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400' :
            'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400'
          }`}>
            {customer.aiJudgment}
          </span>
        </div>
        
        <div className="flex-1 py-4 border-y border-slate-100 dark:border-slate-700/50 my-2 flex flex-col justify-center">
          <div className="flex items-center text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-2">
            <Activity className="w-3 h-3 mr-1 text-brand" />
            关键异常指标
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-300 line-clamp-3 leading-relaxed">
            {customer.keyAbnormal}
          </p>
        </div>
        
        <div className="pt-2 flex items-center justify-between mt-auto">
          <div className="text-[10px] text-slate-400 font-medium">
            最近体检: {customer.lastCheckDate}
          </div>
          <div className="text-xs font-bold text-brand flex items-center group-hover:translate-x-1 transition-transform">
            查看详情 <Zap className="w-3 h-3 ml-1 fill-current" />
          </div>
        </div>
      </div>
    </div>
  );
};

const PillCard: React.FC<{ stat: any; idx: number; isActive: boolean; onClick: () => void }> = ({ stat, idx, isActive, onClick }) => {
  const cardRef = useRef<HTMLDivElement>(null);
  const circleRef = useRef<HTMLSpanElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const hoverContentRef = useRef<HTMLDivElement>(null);
  const tlRef = useRef<gsap.core.Timeline | null>(null);
  const activeTweenRef = useRef<gsap.core.Tween | null>(null);

  useEffect(() => {
    const layout = () => {
      const card = cardRef.current;
      const circle = circleRef.current;
      if (!card || !circle) return;

      const rect = card.getBoundingClientRect();
      const { width: w, height: h } = rect;
      
      // Calculate diameter to cover the entire card from bottom-center
      // Distance to top corners is sqrt((w/2)^2 + h^2)
      const maxDist = Math.sqrt((w / 2) ** 2 + h ** 2);
      const D = Math.ceil(maxDist * 2.5); // Use a multiplier to ensure full coverage including bottom corners
      
      circle.style.width = `${D}px`;
      circle.style.height = `${D}px`;
      circle.style.bottom = `-${D / 2}px`;
      circle.style.left = '50%';

      gsap.set(circle, {
        xPercent: -50,
        scale: 0,
        transformOrigin: '50% 50%'
      });

      const content = contentRef.current;
      const hoverContent = hoverContentRef.current;

      if (content) gsap.set(content, { y: 0 });
      if (hoverContent) gsap.set(hoverContent, { y: h + 12, opacity: 0 });

      tlRef.current?.kill();
      const tl = gsap.timeline({ paused: true });

      tl.to(circle, { scale: 1, duration: 0.6, ease: 'power3.inOut', overwrite: 'auto' }, 0);

      if (content) {
        tl.to(content, { y: -(h + 8), duration: 0.6, ease: 'power3.inOut', overwrite: 'auto' }, 0);
      }

      if (hoverContent) {
        gsap.set(hoverContent, { y: 40, opacity: 0 });
        tl.to(hoverContent, { y: 0, opacity: 1, duration: 0.6, ease: 'power3.inOut', overwrite: 'auto' }, 0);
      }

      tlRef.current = tl;

      // If already active, set to end
      if (isActive) {
        tl.progress(1);
      }
    };

    layout();
    window.addEventListener('resize', layout);
    return () => window.removeEventListener('resize', layout);
  }, []);

  // Sync timeline with isActive state
  useEffect(() => {
    const tl = tlRef.current;
    if (!tl) return;

    if (isActive) {
      activeTweenRef.current?.kill();
      activeTweenRef.current = tl.tweenTo(tl.duration(), {
        duration: 0.4,
        ease: 'power3.out'
      });
    } else {
      // Only reverse if not hovered
      const isHovered = cardRef.current?.matches(':hover');
      if (!isHovered) {
        activeTweenRef.current?.kill();
        activeTweenRef.current = tl.tweenTo(0, {
          duration: 0.3,
          ease: 'power3.inOut'
        });
      }
    }
  }, [isActive]);

  const handleEnter = () => {
    if (isActive) return;
    const tl = tlRef.current;
    if (!tl) return;
    activeTweenRef.current?.kill();
    activeTweenRef.current = tl.tweenTo(tl.duration(), {
      duration: 0.4,
      ease: 'power3.out'
    });
  };

  const handleLeave = () => {
    if (isActive) return;
    const tl = tlRef.current;
    if (!tl) return;
    activeTweenRef.current?.kill();
    activeTweenRef.current = tl.tweenTo(0, {
      duration: 0.3,
      ease: 'power3.inOut'
    });
  };

  return (
    <div 
      ref={cardRef}
      className={`relative ${stat.bg} dark:bg-slate-800 p-6 rounded-2xl border border-slate-100 dark:border-slate-700 shadow-sm overflow-hidden cursor-pointer group transition-all duration-300`}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      onClick={onClick}
    >
      {isActive && (
        <motion.div
          layoutId="pill-nav-active"
          className="absolute inset-0 z-30 pointer-events-none"
          transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
        />
      )}
      <span
        ref={circleRef}
        className={`absolute rounded-full z-[1] block pointer-events-none ${stat.dot}`}
        style={{ willChange: 'transform' }}
        aria-hidden="true"
      />
      
      <div ref={contentRef} className="relative z-10" style={{ willChange: 'transform' }}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <span className={`flex w-2 h-2 rounded-full ${stat.dot}`}></span>
            <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">{stat.label}</p>
          </div>
          <div className={`p-3 rounded-2xl ${stat.dot.replace('bg-', 'bg-').replace('500', '50')} dark:bg-slate-700/50`}>
            <stat.icon className={`w-6 h-6 ${stat.color}`} strokeWidth={2.5} />
          </div>
        </div>
        <h4 className="text-4xl font-extrabold text-slate-800 dark:text-white tracking-tight mb-2">{stat.value}</h4>
        <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">{stat.desc}</p>
      </div>

      <div ref={hoverContentRef} className="absolute inset-0 p-6 z-20 flex flex-col justify-center pointer-events-none" style={{ willChange: 'transform, opacity' }}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <span className="flex w-2 h-2 rounded-full bg-white"></span>
            <p className="text-sm font-semibold text-white/90">{stat.label}</p>
          </div>
          <div className="p-3 bg-white/20 rounded-2xl backdrop-blur-sm">
            <stat.icon className="w-6 h-6 text-white" strokeWidth={2.5} />
          </div>
        </div>
        <h4 className="text-4xl font-extrabold text-white tracking-tight mb-2">{stat.value}</h4>
        <p className="text-xs text-white/80">{stat.desc}</p>
      </div>
    </div>
  );
};

export const AIReportComparisonDetailView: React.FC<{
  setCurrentPage: (page: AppPage) => void;
  isDarkMode: boolean;
  setIsDarkMode: (value: boolean) => void;
}> = ({ setCurrentPage, isDarkMode, setIsDarkMode }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeStat, setActiveStat] = useState(0);
  const [selectedCustomer, setSelectedCustomer] = useState<any | null>(null);
  const [viewMode, setViewMode] = useState<'card' | 'list'>('card');

  const filteredCustomers = useMemo(() => {
    return CUSTOMERS.filter(c => c.name.includes(searchTerm));
  }, [searchTerm]);

  const stats = [
    { label: '总客户数', value: '2,486', color: 'text-blue-500', dot: 'bg-blue-500', desc: '已录入近三年体检数据', icon: Users, bg: 'bg-gradient-to-br from-white to-blue-50 dark:from-slate-800 dark:to-blue-900/20' },
    { label: '本周新增', value: '126', color: 'text-emerald-500', dot: 'bg-emerald-500', desc: '较上周提升 12%', icon: UserPlus, bg: 'bg-gradient-to-br from-white to-emerald-50 dark:from-slate-800 dark:to-emerald-900/20' },
    { label: '异常客户', value: '318', color: 'text-rose-500', dot: 'bg-rose-500', desc: '当前指标超出范围', icon: AlertCircle, bg: 'bg-gradient-to-br from-white to-rose-50 dark:from-slate-800 dark:to-rose-900/20' },
    { label: 'AI预警', value: '73', color: 'text-amber-500', dot: 'bg-amber-500', desc: '建议优先复查与随访', icon: Zap, bg: 'bg-gradient-to-br from-white to-amber-50 dark:from-slate-800 dark:to-amber-900/20' },
  ];

  return (
    <div className="h-full flex flex-col space-y-6 p-6 bg-slate-50 dark:bg-slate-900 transition-colors duration-300 overflow-y-auto">
      <AnimatePresence mode="wait">
        {selectedCustomer ? (
          <motion.div
            key="detail"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3 }}
            className="h-full"
          >
            <AIReportComparisonReportView 
              customer={selectedCustomer} 
              onBack={() => setSelectedCustomer(null)} 
              isDarkMode={isDarkMode}
              setIsDarkMode={setIsDarkMode}
            />
          </motion.div>
        ) : (
          <motion.div
            key="list"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3 }}
            className="flex flex-col space-y-6"
          >
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center space-x-3">
                  <button 
                    onClick={() => setCurrentPage('function-square')}
                    className="p-2 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-lg transition-colors text-slate-500 dark:text-slate-400"
                  >
                    <ArrowLeft className="w-5 h-5" />
                  </button>
                  <h2 className="text-2xl font-bold text-slate-900 dark:text-white">AI报告对比</h2>
                </div>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 ml-11">支持按客户姓名搜索，并进入客户近三年体检报告对比详情。</p>
              </div>
              <div className="flex items-center space-x-2 text-sm">
                <button 
                  onClick={() => setIsDarkMode(!isDarkMode)}
                  className="relative p-2 text-slate-400 dark:text-slate-500 hover:text-brand dark:hover:text-brand-400 hover:bg-brand-light dark:hover:bg-brand-900/30 rounded-xl transition-all mr-2"
                >
                  {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                </button>
                <span className="bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-400 px-3 py-1 rounded-full font-medium">数据范围 2024-2026</span>
                <span className="bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-3 py-1 rounded-full font-medium">最近同步 2026-03-31 09:40</span>
                <span className="bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-3 py-1 rounded-full font-medium">管理员 张永亮</span>
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-4 gap-6">
              {stats.map((stat, idx) => (
                <PillCard key={idx} stat={stat} idx={idx} isActive={activeStat === idx} onClick={() => setActiveStat(idx)} />
              ))}
            </div>

            {/* Filter & Table */}
            <motion.div 
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
              className="flex-1 transition-colors duration-300 mt-2"
            >
              <div className="mb-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white">客户检索与筛选</h3>
                  <div className="flex items-center space-x-4">
                    <div className="flex bg-slate-100 dark:bg-slate-900 p-1 rounded-xl">
                      <button 
                        onClick={() => setViewMode('card')}
                        className={`p-1.5 rounded-lg transition-all ${viewMode === 'card' ? 'bg-white dark:bg-slate-800 text-brand shadow-sm' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'}`}
                        title="卡片展示"
                      >
                        <LayoutGrid className="w-4 h-4" />
                      </button>
                      <button 
                        onClick={() => setViewMode('list')}
                        className={`p-1.5 rounded-lg transition-all ${viewMode === 'list' ? 'bg-white dark:bg-slate-800 text-brand shadow-sm' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'}`}
                        title="列表展示"
                      >
                        <List className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
                      <input
                        type="text"
                        placeholder="输入客户姓名搜索客户"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="pl-9 pr-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 w-64 text-slate-900 dark:text-slate-100 transition-colors"
                      />
                    </div>
                    <button className="px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">高级筛选</button>
                    <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors">导出名单</button>
                  </div>
                </div>
              </div>

              <div className="w-full text-sm">
                {viewMode === 'list' ? (
                  <>
                    <div className="grid grid-cols-12 gap-4 text-slate-400 dark:text-slate-500 text-xs uppercase tracking-wider border-b border-slate-100 dark:border-slate-700 py-4 px-2 font-semibold">
                      <div className="col-span-2 text-left">客户姓名</div>
                      <div className="col-span-2 text-left">性别 / 年龄</div>
                      <div className="col-span-2 text-left">最近体检日期</div>
                      <div className="col-span-2 text-left">AI综合判断</div>
                      <div className="col-span-3 text-left">关键异常指标</div>
                      <div className="col-span-1 text-center">操作</div>
                    </div>
                    
                    <div className="relative h-[600px]">
                      <div className="absolute top-0 left-0 right-0 h-8 bg-gradient-to-b from-white dark:from-slate-800 to-transparent z-10 pointer-events-none transition-colors duration-300"></div>
                      <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-white dark:from-slate-800 to-transparent z-10 pointer-events-none transition-colors duration-300"></div>
                      
                      <div className="w-full h-full overflow-y-auto hide-scrollbar pb-8 pt-2">
                        <AnimatedList className="flex flex-col w-full">
                          {filteredCustomers.map((customer, index) => (
                            <AnimatedRow key={customer.id} customer={customer} index={index} onViewDetails={setSelectedCustomer} />
                          ))}
                        </AnimatedList>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="py-4 h-[750px] overflow-y-auto hide-scrollbar custom-scrollbar pr-2">
                    <AnimatedList className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 w-full">
                      {filteredCustomers.map((customer, index) => (
                        <ReflectiveCard key={customer.id} customer={customer} index={index} onViewDetails={setSelectedCustomer} />
                      ))}
                    </AnimatedList>
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
