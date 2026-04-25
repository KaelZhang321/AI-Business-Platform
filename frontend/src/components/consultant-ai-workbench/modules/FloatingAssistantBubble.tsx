import React from 'react';
import { AnimatePresence, motion } from 'motion/react';
import agentGif from '../../../pages/agent.gif';

/** 悬浮 AI 助手气泡组件属性 */
interface FloatingAssistantBubbleProps {
  /** 助手是否已收缩 */
  isAssistantShrunk: boolean;
  /** 当前悬浮提示文案 */
  aiFloatingTip: string;
  /** 点击展开回调 */
  onExpand: () => void;
}

/** 悬浮 AI 助手气泡组件：在工作台收缩时展示微波浮动的头像入口和提示气泡 */
export const FloatingAssistantBubble: React.FC<FloatingAssistantBubbleProps> = ({
  isAssistantShrunk,
  aiFloatingTip,
  onExpand,
}) => {
  return (
    <AnimatePresence>
      {isAssistantShrunk && (
        <motion.div
          initial={{ scale: 0, opacity: 0, x: -50, y: 50 }}
          animate={{ scale: 1, opacity: 1, x: 0, y: 0 }}
          exit={{ scale: 0, opacity: 0, x: -50, y: 50 }}
          className="absolute bottom-8 left-8 z-50 flex items-end space-x-4"
        >
          <div className="relative">
            <motion.div
              animate={{
                y: [0, -10, 0],
                boxShadow: [
                  '0px 10px 20px -5px rgba(59, 130, 246, 0.4)',
                  '0px 25px 35px -5px rgba(168, 85, 247, 0.6)',
                  '0px 10px 20px -5px rgba(59, 130, 246, 0.4)',
                ],
              }}
              transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
              whileHover={{ scale: 1.1, transition: { duration: 0.2 } }}
              className="relative z-10 flex h-16 w-16 cursor-pointer items-center justify-center overflow-hidden rounded-full border-4 border-white bg-gradient-to-tr from-blue-500 to-purple-500 dark:border-slate-800"
              onClick={onExpand}
              title="点击展开工作台"
            >
              <img src={agentGif} alt="AI Assistant" className="h-full w-full object-cover" />
            </motion.div>
            <motion.div
              animate={{ scale: [1, 1.4, 1], opacity: [0.5, 0, 0.5] }}
              transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
              className="pointer-events-none absolute inset-0 z-0 rounded-full bg-gradient-to-tr from-blue-400 to-purple-400"
            />

            <AnimatePresence>
              {aiFloatingTip && (
                <motion.div
                  initial={{ opacity: 0, y: 10, scale: 0.9 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 10, scale: 0.9 }}
                  className="absolute bottom-full left-full z-50 mb-2 ml-2 whitespace-nowrap rounded-2xl rounded-bl-none border border-slate-100 bg-white px-4 py-2 text-sm text-slate-800 shadow-xl dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                >
                  {aiFloatingTip}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
