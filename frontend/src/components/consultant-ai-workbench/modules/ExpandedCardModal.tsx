import React from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Sparkles, X } from 'lucide-react';
import { AI_CARDS_DATA } from '../../AICards';

/** 卡片放大预览弹窗组件属性 */
interface ExpandedCardModalProps {
  /** 当前放大的卡片 ID（null 表示关闭） */
  expandedCardId: string | null;
  /** 关闭弹窗回调 */
  onClose: () => void;
  /** 各卡片的运行时数据 */
  runtimeDataByCardId?: Record<string, unknown>;
  /** 各卡片的加载状态 */
  runtimeStatusByCardId?: Record<string, 'loading' | 'ready' | 'empty' | 'error'>;
  /** 各卡片的错误信息 */
  runtimeErrorByCardId?: Record<string, string>;
  /** 卡片触发运行时保存（用于 mutation 接口） */
  onRuntimeCardSave?: (cardId: string, payload: Record<string, unknown>) => Promise<void> | void;
}

/** 卡片放大预览弹窗组件：全屏展示单张卡片的详细内容 */
export const ExpandedCardModal: React.FC<ExpandedCardModalProps> = ({
  expandedCardId,
  onClose,
  runtimeDataByCardId = {},
  runtimeStatusByCardId = {},
  runtimeErrorByCardId = {},
  onRuntimeCardSave,
}) => {
  return (
    <AnimatePresence>
      {expandedCardId && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/40 p-6 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            className="flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-3xl bg-white shadow-2xl dark:bg-slate-900"
            onClick={(e) => e.stopPropagation()}
          >
            {(() => {
              const cardData = AI_CARDS_DATA.find((card) => card.id === expandedCardId);
              if (!cardData) {
                return null;
              }
              const CardComponent = cardData.component;
              return (
                <>
                  <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/50 p-6 dark:border-slate-800 dark:bg-slate-800/50">
                    <div className="flex items-center space-x-3">
                      <Sparkles className="h-6 w-6 text-blue-500" />
                      <h3 className="text-2xl font-bold text-slate-900 dark:text-white">{cardData.title}</h3>
                    </div>
                    <button
                      onClick={onClose}
                      className="rounded-full p-2 text-slate-400 transition-colors hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      <X className="h-6 w-6" />
                    </button>
                  </div>
                  <div className="custom-scrollbar flex-1 overflow-y-auto bg-white p-8 dark:bg-slate-900">
                    <CardComponent
                      runtimeData={expandedCardId ? runtimeDataByCardId[expandedCardId] : undefined}
                      runtimeDataByCardId={runtimeDataByCardId}
                      runtimeStatus={expandedCardId ? runtimeStatusByCardId[expandedCardId] : undefined}
                      runtimeError={expandedCardId ? runtimeErrorByCardId[expandedCardId] : undefined}
                      onRuntimeSave={(payload: Record<string, unknown>) => {
                        if (!expandedCardId) {
                          return;
                        }
                        void onRuntimeCardSave?.(expandedCardId, payload);
                      }}
                    />
                  </div>
                </>
              );
            })()}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
