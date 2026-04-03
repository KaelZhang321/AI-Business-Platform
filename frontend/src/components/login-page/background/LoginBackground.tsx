import { motion } from 'motion/react';
import { NeuralFlowBackground } from './NeuralFlowBackground';
import { PhotonParticles } from './PhotonParticles';

// 登录页背景总成：
// 统一组合“深色底层 + 神经流线 + 粒子 + 扫描线 + 噪点纹理”，
// 让主页面只关注业务布局，不再关心背景实现细节。
export function LoginBackground() {
  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden bg-[#010107]">
      {/* 深空基底：提供整体色相与层次 */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,#0a192f_0%,#010107_100%)]" />

      {/* 中景动效：流线 + 光子粒子 */}
      <NeuralFlowBackground />
      <PhotonParticles />

      {/* 远景氛围光 + 网格 + 扫描线 + 噪点，增强“科技感” */}
      <div className="absolute bottom-[-40%] left-[-10%] right-[-10%] h-[80%] bg-[radial-gradient(ellipse_at_bottom,rgba(236,72,153,0.15)_0%,rgba(59,130,246,0.05)_50%,transparent_100%)] rounded-[100%] blur-[120px]" />
      <div className="absolute inset-0 opacity-[0.05] bg-[linear-gradient(to_right,#3b82f6_1px,transparent_1px),linear-gradient(to_bottom,#3b82f6_1px,transparent_1px)] bg-[size:80px_80px]" />

      <motion.div
        animate={{ y: ['0%', '100%', '0%'] }}
        transition={{ duration: 10, repeat: Infinity, ease: 'linear' }}
        className="absolute inset-0 w-full h-[2px] bg-gradient-to-r from-transparent via-cyan-400/20 to-transparent blur-[2px]"
      />

      <div className="absolute top-[-20%] left-[20%] w-[60%] h-[40%] bg-blue-500/10 blur-[100px] rounded-full" />
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none mix-blend-overlay"
        style={{ backgroundImage: 'url("https://grainy-gradients.vercel.app/noise.svg")' }}
      />
    </div>
  );
}
