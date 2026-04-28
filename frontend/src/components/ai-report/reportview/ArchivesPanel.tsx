import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import type { CardSwapRef } from '../CardSwap';
import type { MetricData } from './types';
import { FocusedMetricPanel } from './FocusedMetricPanel';
import { CardStackPanel } from './CardStackPanel';

interface ArchivesPanelProps {
  focusedMetricName: string | null;
  metrics: MetricData[];
  cardStack: string[];
  cardSwapRef: React.RefObject<CardSwapRef | null>;
  viewMode: 'list' | 'trend';
  onChangeViewMode: (mode: 'list' | 'trend') => void;
  onOpenModal: (year: string) => void;
  onSwapCard: () => void;
  onFocusMetric: (metricName: string | null) => void;
}

export const ArchivesPanel: React.FC<ArchivesPanelProps> = ({
  focusedMetricName,
  metrics,
  cardStack,
  cardSwapRef,
  viewMode,
  onChangeViewMode,
  onOpenModal,
  onSwapCard,
  onFocusMetric,
}) => {
  const focusedMetric = metrics.find((m) => m.name === focusedMetricName);
  return (
    <div className="w-full lg:w-2/3 flex flex-col bg-transparent min-h-[500px] overflow-hidden relative">
      <AnimatePresence mode="wait">
        {focusedMetricName ? (
          <motion.div
            key="focused-view"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="absolute inset-0 bg-white dark:bg-slate-900 rounded-[32px] border border-slate-200 dark:border-slate-800 shadow-xl p-8 flex flex-col z-20 overflow-hidden"
          >
            <FocusedMetricPanel metric={focusedMetric} onClose={() => onFocusMetric(null)} />
          </motion.div>
        ) : (
          <CardStackPanel
            cardStack={cardStack}
            viewMode={viewMode}
            onChangeViewMode={onChangeViewMode}
            metrics={metrics}
            cardSwapRef={cardSwapRef}
            onOpenModal={onOpenModal}
            onSwapCard={onSwapCard}
            onFocusMetric={(metricName) => onFocusMetric(metricName)}
          />
        )}
      </AnimatePresence>
    </div>
  );
};
