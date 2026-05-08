import React, { useEffect, useRef } from 'react';
import { motion } from 'motion/react';
import { gsap } from 'gsap';
import type { StatCard } from './types';

interface PillCardProps {
  stat: StatCard;
  isActive: boolean;
  onClick: () => void;
}

export const PillCard: React.FC<PillCardProps> = ({ stat, isActive, onClick }) => {
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

      const maxDist = Math.sqrt((w / 2) ** 2 + h ** 2);
      const diameter = Math.ceil(maxDist * 2.5);

      circle.style.width = `${diameter}px`;
      circle.style.height = `${diameter}px`;
      circle.style.bottom = `-${diameter / 2}px`;
      circle.style.left = '50%';

      gsap.set(circle, {
        xPercent: -50,
        scale: 0,
        transformOrigin: '50% 50%',
      });

      const content = contentRef.current;
      const hoverContent = hoverContentRef.current;

      if (content) {
        gsap.set(content, { y: 0 });
      }

      if (hoverContent) {
        gsap.set(hoverContent, { y: h + 12, opacity: 0 });
      }

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

      if (isActive) {
        tl.progress(1);
      }
    };

    layout();
    window.addEventListener('resize', layout);

    return () => {
      window.removeEventListener('resize', layout);
      activeTweenRef.current?.kill();
      tlRef.current?.kill();
    };
  }, []);

  useEffect(() => {
    const tl = tlRef.current;
    if (!tl) return;

    if (isActive) {
      activeTweenRef.current?.kill();
      activeTweenRef.current = tl.tweenTo(tl.duration(), {
        duration: 0.4,
        ease: 'power3.out',
      });
      return;
    }

    const isHovered = cardRef.current?.matches(':hover');
    if (!isHovered) {
      activeTweenRef.current?.kill();
      activeTweenRef.current = tl.tweenTo(0, {
        duration: 0.3,
        ease: 'power3.inOut',
      });
    }
  }, [isActive]);

  const handleEnter = () => {
    if (isActive) return;
    const tl = tlRef.current;
    if (!tl) return;

    activeTweenRef.current?.kill();
    activeTweenRef.current = tl.tweenTo(tl.duration(), {
      duration: 0.4,
      ease: 'power3.out',
    });
  };

  const handleLeave = () => {
    if (isActive) return;
    const tl = tlRef.current;
    if (!tl) return;

    activeTweenRef.current?.kill();
    activeTweenRef.current = tl.tweenTo(0, {
      duration: 0.3,
      ease: 'power3.inOut',
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
          transition={{ type: 'spring', bounce: 0.2, duration: 0.6 }}
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

      <div
        ref={hoverContentRef}
        className="absolute inset-0 p-6 z-20 flex flex-col justify-center pointer-events-none"
        style={{ willChange: 'transform, opacity' }}
      >
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
