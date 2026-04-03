import { motion } from 'motion/react';

// 光子粒子层：
// 使用大量低成本 div 粒子做“自下而上漂浮”动效，
// 与 NeuralFlowBackground 的路径动效互补，提升空间层次。
export function PhotonParticles() {
  return (
    <div className="absolute inset-0 pointer-events-none">
      {[...Array(40)].map((_, i) => {
        // 每个粒子独立随机起点、颜色、时长和延迟，避免动画同步导致机械感。
        const initialX = Math.random() * 100;
        const initialY = Math.random() * 100;
        const color = Math.random() > 0.5 ? '#06b6d4' : '#ec4899';

        return (
          <motion.div
            key={i}
            className="absolute w-1 h-1 rounded-full blur-[1px]"
            style={{ backgroundColor: color }}
            initial={{
              x: `${initialX}%`,
              y: `${initialY}%`,
              opacity: 0,
            }}
            animate={{
              y: [null, '-100%'],
              opacity: [0, 0.4, 0],
              scale: [0, 1.2, 0],
            }}
            transition={{
              duration: Math.random() * 10 + 15,
              repeat: Infinity,
              ease: 'linear',
              delay: Math.random() * 20,
            }}
          />
        );
      })}
      {/* 中心镂空遮罩：让中间登录卡区域更清晰，减少背景对可读性的干扰。 */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,transparent_10%,rgba(1,1,7,0.7)_85%)]" />
    </div>
  );
}
