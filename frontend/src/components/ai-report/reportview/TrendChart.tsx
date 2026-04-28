import React from 'react';
import type { MetricData } from './types';

interface TrendChartProps {
  m: MetricData;
  yearsToShow?: string[];
  className?: string;
  isExpanded?: boolean;
}

export const TrendChart: React.FC<TrendChartProps> = ({ m, yearsToShow, className, isExpanded }) => {
  const years = yearsToShow || ['2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026'];
  const vals = years.map((y) => Number(m.values[y]));
  const [refMinStr, refMaxStr] = m.refRange.split('-');
  const refMin = parseFloat(refMinStr);
  const refMax = parseFloat(refMaxStr);

  const allVals = [...vals, refMin, refMax].filter((v) => !isNaN(v));
  const min = Math.min(...allVals) * 0.85;
  const max = Math.max(...allVals) * 1.15;
  const range = max - min || 1;

  const width = isExpanded ? 280 : 200;
  const viewBox = isExpanded ? '-30 0 340 55' : '-30 0 260 55';

  const getY = (v: number) => 45 - ((v - min) / range) * 34;
  const getX = (index: number) => (index / (years.length - 1)) * width;

  const yRefMin = getY(refMin);
  const yRefMax = getY(refMax);
  const points = vals.map((v, i) => `${getX(i)},${getY(v)}`).join(' ');

  return (
    <svg viewBox={viewBox} className={`w-full overflow-visible ${className || 'h-20'}`}>
      {!isNaN(yRefMin) && !isNaN(yRefMax) && (
        <rect
          x="0"
          y={yRefMax}
          width={width}
          height={Math.max(0, yRefMin - yRefMax)}
          fill="#10b981"
          fillOpacity="0.06"
          rx="1"
        />
      )}

      {!isNaN(yRefMax) && (
        <>
          <text x="-4" y={yRefMax + 1.5} fontSize={isExpanded ? '5' : '6.5'} fill="#059669" fontWeight="normal" textAnchor="end">
            上限
          </text>
          <line x1="0" y1={yRefMax} x2={width} y2={yRefMax} stroke="#10b981" strokeWidth={isExpanded ? '0.4' : '0.6'} strokeDasharray="3 2" />
          <text x={width + 4} y={yRefMax + 1.5} fontSize={isExpanded ? '5' : '6.5'} fill="#059669" fontWeight="normal" textAnchor="start">
            {refMax}
          </text>
        </>
      )}

      {!isNaN(yRefMin) && (
        <>
          <text x="-4" y={yRefMin + 1.5} fontSize={isExpanded ? '5' : '6.5'} fill="#059669" fontWeight="normal" textAnchor="end">
            下限
          </text>
          <line x1="0" y1={yRefMin} x2={width} y2={yRefMin} stroke="#10b981" strokeWidth={isExpanded ? '0.4' : '0.6'} strokeDasharray="3 2" />
          <text x={width + 4} y={yRefMin + 1.5} fontSize={isExpanded ? '5' : '6.5'} fill="#059669" fontWeight="normal" textAnchor="start">
            {refMin}
          </text>
        </>
      )}

      <polyline
        points={points}
        fill="none"
        stroke="#3b82f6"
        strokeWidth={isExpanded ? '2' : '3.5'}
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {vals.map((v, i) => (
        <g key={i}>
          <circle cx={getX(i)} cy={getY(v)} r={isExpanded ? '2' : '3'} fill="#3b82f6" stroke="#fff" strokeWidth={isExpanded ? '0.8' : '1'} />
          <text x={getX(i)} y={getY(v) - (isExpanded ? 4 : 6)} fontSize={isExpanded ? '6' : '7'} fill="#1d4ed8" textAnchor="middle" fontWeight="medium">
            {v}
          </text>
          <text x={getX(i)} y={53} fontSize={isExpanded ? '5' : '6'} fill="#64748b" textAnchor="middle" fontWeight="medium">
            {years[i]}
          </text>
        </g>
      ))}
    </svg>
  );
};
