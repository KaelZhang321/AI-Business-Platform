import {
  CheckCircle2,
  Eye,
  EyeOff,
  Loader2,
  MessageCircle,
  QrCode,
  RefreshCw,
  Send,
  ShieldCheck,
  Smartphone,
  User,
} from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import type { FormEvent } from 'react';
import { InputField } from '../InputField';
import type { LoginErrors, LoginMethod } from '../types';

// 登录内容面板参数：
// 该组件是“纯展示 + 事件透传”层，不保存业务状态，便于复用与测试。
interface LoginMethodPanelProps {
  method: LoginMethod;
  errors: LoginErrors;
  email: string;
  password: string;
  captcha: string;
  phone: string;
  code: string;
  showPassword: boolean;
  rememberMe: boolean;
  isLoading: boolean;
  isCodeLoading: boolean;
  countdown: number;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onCaptchaChange: (value: string) => void;
  onPhoneChange: (value: string) => void;
  onCodeChange: (value: string) => void;
  onShowPasswordToggle: () => void;
  onRememberMeToggle: () => void;
  onSubmit: (event: FormEvent) => void;
  onGetCode: () => Promise<void> | void;
  onIamRedirect: () => void;
}

// 统一切换动画参数，确保各登录方式切换体感一致。
const panelTransition = { duration: 1.2, ease: [0.19, 1, 0.22, 1] as [number, number, number, number] };

// 登录方式主面板：
// 根据 method 渲染 5 种视图（account/mobile/qrcode/wechat/dingtalk）。
export function LoginMethodPanel({
  method,
  errors,
  email,
  password,
  captcha,
  phone,
  code,
  showPassword,
  rememberMe,
  isLoading,
  isCodeLoading,
  countdown,
  onEmailChange,
  onPasswordChange,
  onCaptchaChange,
  onPhoneChange,
  onCodeChange,
  onShowPasswordToggle,
  onRememberMeToggle,
  onSubmit,
  onGetCode,
  onIamRedirect,
}: LoginMethodPanelProps) {
  return (
    <div className="relative h-[380px]">
      {/* mode="wait"：先出场再进场，避免多面板叠在一起造成闪烁 */}
      <AnimatePresence mode="wait" initial={false}>
        {/* 账号密码登录：唯一接入真实 onLogin 的入口 */}
        {method === 'account' && (
          <motion.form
            key="account"
            initial={{ opacity: 0, x: 40, scale: 0.92, filter: 'blur(40px)' }}
            animate={{ opacity: 1, x: 0, scale: 1, filter: 'blur(0px)' }}
            exit={{ opacity: 0, x: -40, scale: 1.08, filter: 'blur(40px)' }}
            transition={panelTransition}
            onSubmit={onSubmit}
            className="space-y-4 absolute inset-0"
          >
            {/* 基础账号字段 */}
            <InputField
              label="Employee ID"
              placeholder="工号或企业邮箱"
              value={email}
              onChange={(e) => onEmailChange(e.target.value)}
              error={errors.email}
              icon={User}
            />
            <InputField
              label="Password"
              type={showPassword ? 'text' : 'password'}
              placeholder="内网登录密码"
              value={password}
              onChange={(e) => onPasswordChange(e.target.value)}
              error={errors.password}
              icon={ShieldCheck}
              rightElement={
                <button type="button" onClick={onShowPasswordToggle} className="text-white/20 hover:text-white/60 transition-colors">
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              }
            />
            <div className="flex gap-4 items-end">
              {/* 验证码当前是静态占位，后续可替换成真实图片接口 */}
              <InputField label="Captcha" placeholder="验证码" value={captcha} onChange={(e) => onCaptchaChange(e.target.value)} error={errors.captcha} />
              <div className="w-32 h-[48px] bg-white/[0.05] rounded-2xl flex items-center justify-center cursor-pointer border border-white/15 text-blue-300 font-mono font-bold tracking-[0.2em] text-sm transition-all group/captcha shadow-inner">
                <span>4X9K</span>
              </div>
            </div>

            {errors.general ? (
              <div className="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs font-medium text-red-200">
                {/* 通用错误（接口返回或非字段级错误）集中展示在按钮上方。 */}
                {errors.general}
              </div>
            ) : null}

            {/* 辅助选项区：记住我 + 忘记密码 */}
            <div className="flex items-center justify-between px-1 pt-2">
              <label className="flex items-center gap-3 cursor-pointer group/check">
                <div
                  className={`w-5 h-5 rounded-lg border flex items-center justify-center transition-all duration-500 ${
                    rememberMe ? 'bg-blue-500 border-blue-500 shadow-[0_0_20px_rgba(59,130,246,0.7)]' : 'border-white/20'
                  }`}
                >
                  <input type="checkbox" className="hidden" checked={rememberMe} onChange={onRememberMeToggle} />
                  {rememberMe && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
                </div>
                <span className="text-[11px] text-white/50 select-none transition-colors font-semibold">保持登录状态</span>
              </label>
              <button type="button" className="text-[11px] font-bold text-blue-400/60 transition-colors">
                忘记密码？
              </button>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-4 rounded-full font-bold text-white bg-gradient-to-r from-blue-500 to-blue-600 shadow-[0_25px_50px_rgba(59,130,246,0.4)] active:scale-[0.98] transition-all flex items-center justify-center gap-2.5 text-sm mt-4 border border-white/20"
            >
              {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : '进入系统'}
            </button>

            {/* IAM SSO 跳转入口 */}
            <div className="relative mt-8 mb-4">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-white/10"></div>
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-[#000000] px-2 text-white/50 uppercase tracking-widest text-[9px]">OR</span>
              </div>
            </div>

            <button
              type="button"
              onClick={onIamRedirect}
              disabled={isLoading}
              className="w-full py-4 rounded-full font-bold text-slate-800 bg-white hover:bg-slate-200 transition-all flex items-center justify-center gap-2.5 text-sm cursor-pointer shadow-[0_0_20px_rgba(255,255,255,0.1)] active:scale-[0.98]"
            >
              <ShieldCheck className="w-5 h-5 text-blue-600" />
              使用企业统一认证 (IAM) 登录
            </button>
          </motion.form>
        )}

        {/* 手机/邮箱验证码登录：当前只保留交互流程，后端可后续接入 */}
        {method === 'mobile' && (
          <motion.form
            key="mobile"
            initial={{ opacity: 0, x: 40, scale: 0.92, filter: 'blur(40px)' }}
            animate={{ opacity: 1, x: 0, scale: 1, filter: 'blur(0px)' }}
            exit={{ opacity: 0, x: -40, scale: 1.08, filter: 'blur(40px)' }}
            transition={panelTransition}
            onSubmit={onSubmit}
            className="space-y-4 absolute inset-0"
          >
            <InputField
              label="Phone / Email"
              placeholder="请输入手机号或邮箱"
              value={phone}
              onChange={(e) => onPhoneChange(e.target.value)}
              error={errors.phone}
              icon={Smartphone}
            />
            <div className="flex gap-4 items-end">
              <InputField label="Verification Code" placeholder="验证码" value={code} onChange={(e) => onCodeChange(e.target.value)} error={errors.code} />
              <button
                type="button"
                onClick={onGetCode}
                disabled={isCodeLoading || countdown > 0}
                className="w-32 h-[48px] bg-white/[0.05] rounded-2xl flex items-center justify-center border border-white/15 text-blue-400 text-[11px] font-bold hover:bg-white/[0.12] transition-all shadow-inner disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isCodeLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : countdown > 0 ? `${countdown}s 后重新获取` : '获取验证码'}
              </button>
            </div>

            {/* 保留高度，维持与账号登录面板视觉重心一致 */}
            <div className="h-16" />

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-4 rounded-full font-bold text-white bg-gradient-to-r from-blue-500 to-blue-600 shadow-[0_25px_50px_rgba(59,130,246,0.4)] active:scale-[0.98] transition-all flex items-center justify-center gap-2.5 text-sm border border-white/20"
            >
              {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : '验证并登录'}
            </button>
          </motion.form>
        )}

        {/* App 扫码登录面板 */}
        {method === 'qrcode' && (
          <motion.div
            key="qrcode"
            initial={{ opacity: 0, x: 40, scale: 0.92, filter: 'blur(40px)' }}
            animate={{ opacity: 1, x: 0, scale: 1, filter: 'blur(0px)' }}
            exit={{ opacity: 0, x: -40, scale: 1.08, filter: 'blur(40px)' }}
            transition={panelTransition}
            className="flex flex-col items-center justify-center py-10 space-y-10 absolute inset-0"
          >
            <div className="relative p-7 bg-white rounded-[44px] shadow-[0_0_100px_rgba(255,255,255,0.1)] group/qr">
              <div className="w-48 h-48 bg-slate-50 flex items-center justify-center overflow-hidden rounded-[32px]">
                <QrCode className="w-40 h-40 text-slate-800" />
              </div>
              <div className="absolute inset-0 bg-black/80 backdrop-blur-2xl opacity-0 transition-all duration-700 flex flex-col items-center justify-center rounded-[44px] cursor-pointer">
                <RefreshCw className="w-14 h-14 text-white mb-4 animate-spin-slow" />
                <span className="text-xs text-white font-bold tracking-[0.3em]">REFRESH</span>
              </div>
            </div>
            <div className="text-center">
              <p className="text-sm text-white font-bold tracking-wider">使用丽滋医疗 App 扫码登录</p>
              <p className="text-[11px] text-white/40 mt-4 font-bold uppercase tracking-[0.3em]">Secure · Instant · Passwordless</p>
            </div>
          </motion.div>
        )}

        {/* 微信扫码登录面板 */}
        {method === 'wechat' && (
          <motion.div
            key="wechat"
            initial={{ opacity: 0, x: 40, scale: 0.92, filter: 'blur(40px)' }}
            animate={{ opacity: 1, x: 0, scale: 1, filter: 'blur(0px)' }}
            exit={{ opacity: 0, x: -40, scale: 1.08, filter: 'blur(40px)' }}
            transition={panelTransition}
            className="flex flex-col items-center justify-center py-10 space-y-10 absolute inset-0"
          >
            <div className="relative p-7 bg-white rounded-[44px] shadow-[0_0_100px_rgba(7,193,96,0.2)] group/qr">
              <div className="w-48 h-48 bg-slate-50 flex items-center justify-center overflow-hidden rounded-[32px] relative">
                <QrCode className="w-40 h-40 text-slate-800" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-12 h-12 bg-white rounded-xl shadow-lg flex items-center justify-center border border-slate-100">
                    <MessageCircle className="w-8 h-8 text-[#07C160]" />
                  </div>
                </div>
              </div>
              <div className="absolute inset-0 bg-black/80 backdrop-blur-2xl opacity-0 transition-all duration-700 flex flex-col items-center justify-center rounded-[44px] cursor-pointer">
                <RefreshCw className="w-14 h-14 text-white mb-4 animate-spin-slow" />
                <span className="text-xs text-white font-bold tracking-[0.3em]">REFRESH</span>
              </div>
            </div>
            <div className="text-center">
              <p className="text-sm text-white font-bold tracking-wider">使用微信扫码登录</p>
              <p className="text-[11px] text-white/40 mt-4 font-bold uppercase tracking-[0.3em]">WeChat · Secure · Fast</p>
            </div>
          </motion.div>
        )}

        {/* 钉钉扫码登录面板 */}
        {method === 'dingtalk' && (
          <motion.div
            key="dingtalk"
            initial={{ opacity: 0, x: 40, scale: 0.92, filter: 'blur(40px)' }}
            animate={{ opacity: 1, x: 0, scale: 1, filter: 'blur(0px)' }}
            exit={{ opacity: 0, x: -40, scale: 1.08, filter: 'blur(40px)' }}
            transition={panelTransition}
            className="flex flex-col items-center justify-center py-10 space-y-10 absolute inset-0"
          >
            <div className="relative p-7 bg-white rounded-[44px] shadow-[0_0_100px_rgba(0,137,255,0.2)] group/qr">
              <div className="w-48 h-48 bg-slate-50 flex items-center justify-center overflow-hidden rounded-[32px] relative">
                <QrCode className="w-40 h-40 text-slate-800" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-12 h-12 bg-white rounded-xl shadow-lg flex items-center justify-center border border-slate-100">
                    <Send className="w-8 h-8 text-[#0089FF]" />
                  </div>
                </div>
              </div>
              <div className="absolute inset-0 bg-black/80 backdrop-blur-2xl opacity-0 transition-all duration-700 flex flex-col items-center justify-center rounded-[44px] cursor-pointer">
                <RefreshCw className="w-14 h-14 text-white mb-4 animate-spin-slow" />
                <span className="text-xs text-white font-bold tracking-[0.3em]">REFRESH</span>
              </div>
            </div>
            <div className="text-center">
              <p className="text-sm text-white font-bold tracking-wider">使用钉钉扫码登录</p>
              <p className="text-[11px] text-white/40 mt-4 font-bold uppercase tracking-[0.3em]">DingTalk · Enterprise · Secure</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
