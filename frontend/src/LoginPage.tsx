/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { ShieldAlert, Loader2, Sparkles, RefreshCw } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useState, type MouseEvent, useRef } from 'react';
import { FontLoader } from './components/login-page/FontLoader';
import { LoginBackground } from './components/login-page/background/LoginBackground';
import type { LoginPageProps } from './components/login-page/types';

// 登录页主容器（编排层）：
// 当前仅保留 IAM 统一认证流程
export function LoginPage({ onIamLogin }: LoginPageProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // 页面视觉状态（点击涟漪）
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isClicking, setIsClicking] = useState(false);

  const hasRequestedRef = useRef(false); // 新增一个锁记录，脱离组件重绘影响

  // IAM SSO 跳转处理
  const handleIamRedirect = () => {
    setIsLoading(true);
    setErrorMsg(null);
    const IAM_AUTH_URL = import.meta.env.VITE_IAM_AUTH_URL || 'https://beta-crm.ssss818.com/iam/';
    const CLIENT_ID = import.meta.env.VITE_IAM_CLIENT_ID || 'AI-RND-WORKFLOW';
    // 明确告诉 IAM 授权后回调到当前组件挂载的路由
    // 本地开发模式去根目录，线上带上 /ai-platform 子路径配置
    const basePath = import.meta.env.DEV ? '' : '/ai-platform';
    const REDIRECT_URI = window.location.origin + basePath + '/login';
    const targetUrl = `${IAM_AUTH_URL}?appCode=${CLIENT_ID}&redirectUrl=${encodeURIComponent(REDIRECT_URI)}&response_type=code`;
    window.location.href = targetUrl;
  };

  // 初始化检测 URL 中的授权码
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const errorCode = params.get('error');
    const token = localStorage.getItem('ai_platform_token')


    if (errorCode) {
      setErrorMsg(`统一认证返回错误: ${errorCode}`);
      setIsLoading(false);
      return;
    }

    if (code && onIamLogin) {
      // 👇 在这里拦截，如果已经发过一次请求就不继续发送
      if (hasRequestedRef.current) return;
      hasRequestedRef.current = true; // 马上锁住
      // 执行系统登录流程
      onIamLogin(code).catch((err) => {
        const message = err instanceof Error ? err.message : '授权码解析与系统登录失败';
        setErrorMsg(message);
        setIsLoading(false);
      });
      return;
    }

    if (!code) {
      // 若参数里没有 code ，并且在登录页内，说明触发了未登录拦截，那么直接自动去 IAM 系统登录
      handleIamRedirect();
    }
  }, [onIamLogin]);

  // 记录鼠标在容器内位置，用于点击时绘制全局光晕涟漪。
  const handleMouseMove = (event: MouseEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setMousePos({
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    });
  };

  return (
    <div
      className="min-h-screen w-full bg-[#010107] flex items-center justify-center p-4 font-sans selection:bg-blue-500/30 selection:text-white overflow-hidden relative"
      onMouseMove={handleMouseMove}
      onMouseDown={() => setIsClicking(true)}
      onMouseUp={() => setIsClicking(false)}
    >
      {/* 局部字体注入，确保登录页独立样式一致 */}
      <FontLoader />

      {/* 点击涟漪：提升页面“有响应”的反馈感 */}
      <AnimatePresence>
        {isClicking && (
          <motion.div
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 0.3, scale: 1.2 }}
            exit={{ opacity: 0, scale: 1.5 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className="fixed pointer-events-none z-[60] rounded-full blur-[100px] bg-blue-400/20"
            style={{
              left: mousePos.x,
              top: mousePos.y,
              width: '400px',
              height: '400px',
              transform: 'translate(-50%, -50%)',
            }}
          />
        )}
      </AnimatePresence>

      {/* 背景层总成（深空底、网格、流线、粒子、扫描线） */}
      <LoginBackground />

      {/* 主卡片容器入场动画 */}
      <motion.div
        initial={{ opacity: 0, scale: 0.98, y: 40 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 1.5, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="relative group">
          {/* 外层动态氛围光 */}
          <motion.div
            animate={{ opacity: [0.1, 0.4, 0.1] }}
            transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
            className="absolute -inset-[15px] rounded-[55px] blur-[20px] pointer-events-none"
            style={{
              background:
                'radial-gradient(circle at 0% 0%, rgba(34,211,238,0.5) 0%, transparent 40%), radial-gradient(circle at 100% 100%, rgba(34,211,238,0.5) 0%, transparent 40%)',
            }}
          />

          {/* 外圈折射边缘高光 */}
          <motion.div
            animate={{
              opacity: [0.4, 0.8, 0.4],
              filter: [
                'drop-shadow(0 0 4px rgba(34,211,238,0.3))',
                'drop-shadow(0 0 16px rgba(34,211,238,0.6))',
                'drop-shadow(0 0 4px rgba(34,211,238,0.3))',
              ],
            }}
            transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
            className="absolute -inset-[1px] rounded-[41px] pointer-events-none p-[1px]"
            style={{
              background: 'linear-gradient(135deg, rgba(34,211,238,1) 0%, rgba(34,211,238,0) 50%, rgba(34,211,238,1) 100%)',
              WebkitMask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
              WebkitMaskComposite: 'xor',
              maskComposite: 'exclude',
            }}
          />

          <div className="relative rounded-[40px] shadow-[0_120px_240px_-60px_rgba(0,0,0,1),inset_0_0_0_1.5px_rgba(255,255,255,0.05)] bg-[#0d111c]/30 backdrop-blur-[120px] overflow-hidden flex flex-col p-10 items-center justify-center min-h-[400px]">
            {/* 品牌区域 */}
            <div className="flex flex-col items-center gap-4 mb-10 z-10">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-blue-800 rounded-3xl flex items-center justify-center shadow-[0_15px_40px_rgba(37,99,235,0.4)] border border-white/30 relative overflow-hidden transition-all duration-500">
                <div className="absolute inset-0 bg-gradient-to-tr from-white/40 to-transparent opacity-0 transition-opacity duration-500" />
                <div className="flex flex-col items-center">
                  <Sparkles className="text-white w-7 h-7 relative z-10" />
                  <span className="text-[8px] text-white/60 font-bold uppercase tracking-tighter mt-0.5">AI</span>
                </div>
              </div>
              <div className="flex flex-col text-center">
                <h2 className="text-xl font-bold text-white tracking-tight leading-tight">AI 业务工作台</h2>
                <p className="text-[11px] text-white/40 uppercase tracking-[0.4em] font-bold mt-1">Enterprise Unified Auth</p>
              </div>
            </div>

            {/* 交互状态展示 */}
            <div className="flex flex-col items-center w-full z-10">
              {errorMsg ? (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center w-full">
                  <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mb-6">
                    <ShieldAlert className="w-8 h-8 text-red-500/80" />
                  </div>
                  <div className="rounded-2xl border border-red-500/30 bg-red-500/10 px-6 py-4 text-sm font-medium text-red-200 text-center w-full mb-8">
                    {errorMsg}
                  </div>
                  <button
                    type="button"
                    onClick={handleIamRedirect}
                    className="w-full py-4 rounded-full font-bold text-slate-800 bg-white hover:bg-slate-200 transition-all flex items-center justify-center gap-2.5 text-sm cursor-pointer shadow-[0_0_20px_rgba(255,255,255,0.1)] active:scale-[0.98]"
                  >
                    <RefreshCw className="w-5 h-5 text-blue-600" />
                    重试 IAM 单点登录
                  </button>
                </motion.div>
              ) : (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center">
                  <div className="relative w-20 h-20 mb-6 flex items-center justify-center">
                    <div className="absolute inset-0 rounded-full border border-blue-500/30 animate-[spin_3s_linear_infinite]" />
                    <div className="absolute inset-2 rounded-full border border-blue-400/50 border-t-transparent animate-[spin_1.5s_linear_infinite]" />
                    <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
                  </div>
                  <p className="text-sm font-bold text-white/70 tracking-widest uppercase">
                    正在对接统一认证中心...
                  </p>
                </motion.div>
              )}
            </div>
          </div>
        </div>
      </motion.div>

      {/* 页脚版权信息 */}
      <div className="fixed bottom-8 left-0 right-0 flex flex-col items-center gap-2 pointer-events-none opacity-20">
        <p className="text-[9px] uppercase tracking-[0.4em] text-white font-medium">© 2026 LIZHI ZHISHU TECHNOLOGY. SECURED BY AI.</p>
      </div>
    </div>
  );
}
