import React, { useRef, useEffect, useCallback } from 'react';
import gsap from 'gsap';

/** 液滴光标组件属性：控制光标形状、颜色、拖尾和动画参数 */
export interface BlobCursorProps {
  /** 光标形状：圆形 / 方形 */
  blobType?: 'circle' | 'square';
  /** 填充色 */
  fillColor?: string;
  /** 拖尾数量 */
  trailCount?: number;
  /** 各层尺寸数组 */
  sizes?: number[];
  /** 各层内圈尺寸数组 */
  innerSizes?: number[];
  /** 内圈颜色 */
  innerColor?: string;
  /** 各层透明度 */
  opacities?: number[];
  /** 阴影颜色 */
  shadowColor?: string;
  /** 阴影模糊半径 */
  shadowBlur?: number;
  shadowOffsetX?: number;
  shadowOffsetY?: number;
  /** SVG 滤镜 ID */
  filterId?: string;
  /** 滤镜高斯模糊偏差 */
  filterStdDeviation?: number;
  filterColorMatrixValues?: string;
  /** 是否启用 SVG 液滴融合滤镜 */
  useFilter?: boolean;
  /** 主光标动画时长（秒） */
  fastDuration?: number;
  /** 拖尾动画时长（秒） */
  slowDuration?: number;
  fastEase?: string;
  slowEase?: string;
  /** 层叠顺序 */
  zIndex?: number;
  children?: React.ReactNode;
  className?: string;
}

/** 液滴光标组件：基于 GSAP 的光标跟随动画，支持多层拖尾和 SVG 液滴融合效果 */
export default function BlobCursor({
  blobType = 'circle',
  fillColor = '#5227FF',
  trailCount = 3,
  sizes = [60, 125, 75],
  innerSizes = [20, 35, 25],
  innerColor = 'rgba(255,255,255,0.8)',
  opacities = [0.6, 0.6, 0.6],
  shadowColor = 'rgba(0,0,0,0.75)',
  shadowBlur = 5,
  shadowOffsetX = 10,
  shadowOffsetY = 10,
  filterId = 'blob',
  filterStdDeviation = 30,
  filterColorMatrixValues = '1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 35 -10',
  useFilter = true,
  fastDuration = 0.1,
  slowDuration = 0.5,
  fastEase = 'power3.out',
  slowEase = 'power1.out',
  zIndex = 100,
  children,
  className = "relative w-full h-full"
}: BlobCursorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const blobsRef = useRef<(HTMLDivElement | null)[]>([]);

  const updateOffset = useCallback(() => {
    if (!containerRef.current) return { left: 0, top: 0 };
    const rect = containerRef.current.getBoundingClientRect();
    return { left: rect.left, top: rect.top };
  }, []);

  const handleMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement> | React.TouchEvent<HTMLDivElement>) => {
      const { left, top } = updateOffset();
      const x = 'clientX' in e ? e.clientX : e.touches[0].clientX;
      const y = 'clientY' in e ? e.clientY : e.touches[0].clientY;

      blobsRef.current.forEach((el, i) => {
        if (!el) return;
        const isLead = i === 0;
        gsap.to(el, {
          x: x - left,
          y: y - top,
          duration: isLead ? fastDuration : slowDuration,
          ease: isLead ? fastEase : slowEase
        });
      });
    },
    [updateOffset, fastDuration, slowDuration, fastEase, slowEase]
  );

  useEffect(() => {
    const onResize = () => updateOffset();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [updateOffset]);

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMove}
      onTouchMove={handleMove}
      className={className}
      style={{ zIndex }}
    >
      {useFilter && (
        <svg className="absolute w-0 h-0">
          <filter id={filterId}>
            <feGaussianBlur in="SourceGraphic" result="blur" stdDeviation={filterStdDeviation} />
            <feColorMatrix in="blur" values={filterColorMatrixValues} />
          </filter>
        </svg>
      )}

      <div
        className="pointer-events-none absolute inset-0 overflow-hidden select-none cursor-default"
        style={{ filter: useFilter ? `url(#${filterId})` : undefined }}
      >
        {Array.from({ length: trailCount }).map((_, i) => (
          <div
            key={i}
            ref={el => {
              blobsRef.current[i] = el;
            }}
            className="absolute will-change-transform transform -translate-x-1/2 -translate-y-1/2"
            style={{
              width: sizes[i],
              height: sizes[i],
              borderRadius: blobType === 'circle' ? '50%' : '0',
              backgroundColor: fillColor,
              opacity: opacities[i],
              boxShadow: `${shadowOffsetX}px ${shadowOffsetY}px ${shadowBlur}px 0 ${shadowColor}`
            }}
          >
            <div
              className="absolute"
              style={{
                width: innerSizes[i],
                height: innerSizes[i],
                top: (sizes[i] - innerSizes[i]) / 2,
                left: (sizes[i] - innerSizes[i]) / 2,
                backgroundColor: innerColor,
                borderRadius: blobType === 'circle' ? '50%' : '0'
              }}
            />
          </div>
        ))}
      </div>
      {children}
    </div>
  );
}
