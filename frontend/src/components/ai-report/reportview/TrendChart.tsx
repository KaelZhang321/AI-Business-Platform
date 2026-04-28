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
  const valuePoints = years
    .map((year, index) => {
      const rawValue = m.values[year];
      const numericValue = typeof rawValue === 'number' ? rawValue : Number(rawValue);
      return Number.isFinite(numericValue) ? { year, index, value: numericValue } : null;
    })
    .filter((point): point is { year: string; index: number; value: number } => Boolean(point));
  const [refMinStr, refMaxStr] = m.refRange.split('-');
  const refMin = parseFloat(refMinStr);
  const refMax = parseFloat(refMaxStr);

  const allVals = [...valuePoints.map((point) => point.value), refMin, refMax].filter((v) => Number.isFinite(v));
  const fallbackValue = valuePoints[0]?.value ?? 0;
  const min = (allVals.length > 0 ? Math.min(...allVals) : fallbackValue) * 0.85;
  const max = (allVals.length > 0 ? Math.max(...allVals) : fallbackValue) * 1.15;
  const range = max - min || 1;

  const width = isExpanded ? 280 : 200;
  const viewBox = isExpanded ? '-30 0 340 55' : '-30 0 260 55';

  const getY = (v: number) => 45 - ((v - min) / range) * 34;
  const getX = (index: number) => years.length > 1 ? (index / (years.length - 1)) * width : width / 2;

  const yRefMin = getY(refMin);
  const yRefMax = getY(refMax);
  const points = valuePoints.map((point) => `${getX(point.index)},${getY(point.value)}`).join(' ');

  return (
    <svg viewBox={viewBox} className={`w-full overflow-visible ${className || 'h-20'}`}>
      {Number.isFinite(yRefMin) && Number.isFinite(yRefMax) && (
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

      {Number.isFinite(yRefMax) && (
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

      {Number.isFinite(yRefMin) && (
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

      {points ? (
        <polyline
          points={points}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={isExpanded ? '2' : '3.5'}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ) : (
        <text x={width / 2} y="30" fontSize={isExpanded ? '6' : '7'} fill="#94a3b8" textAnchor="middle">
          暂无趋势数据
        </text>
      )}

      {valuePoints.map((point) => (
        <g key={point.year}>
          <circle cx={getX(point.index)} cy={getY(point.value)} r={isExpanded ? '2' : '3'} fill="#3b82f6" stroke="#fff" strokeWidth={isExpanded ? '0.8' : '1'} />
          <text x={getX(point.index)} y={getY(point.value) - (isExpanded ? 4 : 6)} fontSize={isExpanded ? '6' : '7'} fill="#1d4ed8" textAnchor="middle" fontWeight="medium">
            {point.value}
          </text>
          <text x={getX(point.index)} y={53} fontSize={isExpanded ? '5' : '6'} fill="#64748b" textAnchor="middle" fontWeight="medium">
            {point.year}
          </text>
        </g>
      ))}
    </svg>
  );
};
