import React from 'react';
import { PillCard } from './PillCard';
import type { StatCard } from './types';

interface StatsGridProps {
  stats: StatCard[];
  activeStat: number;
  onSelectStat: (index: number) => void;
}

export const StatsGrid: React.FC<StatsGridProps> = ({ stats, activeStat, onSelectStat }) => {
  return (
    <div className="grid grid-cols-4 gap-6">
      {stats.map((stat, idx) => (
        <PillCard key={idx} stat={stat} isActive={activeStat === idx} onClick={() => onSelectStat(idx)} />
      ))}
    </div>
  );
};
