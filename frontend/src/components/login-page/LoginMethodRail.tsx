import { MessageCircle, QrCode, Send, Smartphone, User } from 'lucide-react';
import { motion } from 'motion/react';
import { useRef, type ChangeEvent } from 'react';
import type { LoginMethod, SocialLoginMethod } from './types';

// 右侧登录方式切换轨 props：
// 该组件只负责“展示与切换入口”，具体登录逻辑由父组件承接。
interface LoginMethodRailProps {
  method: LoginMethod;
  hoveredMethod: LoginMethod | null;
  wechatIconUrl: string | null;
  dingtalkIconUrl: string | null;
  onMethodChange: (method: LoginMethod) => void;
  onHoveredMethodChange: (method: LoginMethod | null) => void;
  onSocialIconUpload: (e: ChangeEvent<HTMLInputElement>, type: SocialLoginMethod) => void;
}

// 主登录方式（顶部）与社交方式（底部）拆开管理，便于扩展与样式编排。
const baseMethods: LoginMethod[] = ['account', 'mobile', 'qrcode'];
const socialMethods: SocialLoginMethod[] = ['wechat', 'dingtalk'];

// 登录方式切换轨：
// - 单击：切换登录方式
// - 双击（社交项）：上传自定义图标
// - 悬停：显示气泡提示
export function LoginMethodRail({
  method,
  hoveredMethod,
  wechatIconUrl,
  dingtalkIconUrl,
  onMethodChange,
  onHoveredMethodChange,
  onSocialIconUpload,
}: LoginMethodRailProps) {
  // 使用 ref 触发隐藏 input，保持轨道按钮纯视觉形态。
  const wechatInputRef = useRef<HTMLInputElement | null>(null);
  const dingtalkInputRef = useRef<HTMLInputElement | null>(null);

  return (
    <div className="w-20 flex flex-col items-center py-10 gap-4 relative z-10">
      {/* 轨道分隔线：与左侧内容区建立视觉边界 */}
      <div className="absolute top-0 bottom-0 left-0 w-[1px] bg-gradient-to-b from-transparent via-white/40 to-transparent" />

      {/* 顶部：账号/手机/扫码三种主入口 */}
      {baseMethods.map((currentMethod) => (
        <button
          key={currentMethod}
          onClick={() => onMethodChange(currentMethod)}
          onMouseEnter={() => onHoveredMethodChange(currentMethod)}
          onMouseLeave={() => onHoveredMethodChange(null)}
          className={`
            relative w-13 h-13 rounded-[24px] flex items-center justify-center transition-all duration-700 group
            ${method === currentMethod ? 'text-white' : 'text-white/20 hover:text-white/60 hover:bg-white/5'}
          `}
        >
          {/* 激活态液态高光，使用 layoutId 保证切换时平滑过渡 */}
          {method === currentMethod && (
            <motion.div
              layoutId="activeLiquidTab"
              className="absolute inset-0 bg-white/[0.22] backdrop-blur-[100px] rounded-[24px] border border-white/70 shadow-[inset_0_0_35px_rgba(255,255,255,0.35),0_30px_60px_rgba(0,0,0,0.6)]"
              transition={{
                type: 'spring',
                stiffness: 120,
                damping: 14,
                mass: 2.2,
              }}
            >
              <div className="absolute inset-0 rounded-[24px] border-t border-white/90 opacity-95" />
              <div className="absolute inset-0 rounded-[24px] bg-gradient-to-b from-white/40 to-transparent opacity-70" />
            </motion.div>
          )}

          <motion.div
            className="relative z-10"
            animate={{
              scale: method === currentMethod ? 1.25 : 1,
              rotate: method === currentMethod ? 0 : -10,
            }}
            transition={{ type: 'spring', stiffness: 300, damping: 15 }}
          >
            {currentMethod === 'account' && <User className="w-6 h-6" />}
            {currentMethod === 'mobile' && <Smartphone className="w-6 h-6" />}
            {currentMethod === 'qrcode' && <QrCode className="w-6 h-6" />}
          </motion.div>

          {/* 悬浮提示文案：帮助用户理解图标语义 */}
          <div
            className={`absolute left-full ml-6 px-5 py-3 bg-[#0d111c]/95 backdrop-blur-3xl rounded-2xl border border-white/25 text-[11px] font-bold text-white transition-all duration-300 pointer-events-none whitespace-nowrap z-50 shadow-[0_30px_60px_rgba(0,0,0,0.7)] ${
              hoveredMethod === currentMethod ? 'opacity-100 ml-8' : 'opacity-0'
            }`}
          >
            <div className="flex items-center gap-3.5">
              <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_12px_rgba(59,130,246,1)]" />
              {currentMethod === 'account' ? '账号登录' : currentMethod === 'mobile' ? '手机登录' : '扫码登录'}
            </div>
          </div>
        </button>
      ))}

      <div className="flex-grow" />
      <div className="w-8 h-[1px] bg-white/10 my-2" />

      {/* 底部：社交扫码入口（支持自定义图标） */}
      {socialMethods.map((socialMethod) => (
        <div key={socialMethod} className="relative group">
          <button
            onClick={() => onMethodChange(socialMethod)}
            onMouseEnter={() => onHoveredMethodChange(socialMethod)}
            onMouseLeave={() => onHoveredMethodChange(null)}
            onDoubleClick={() => (socialMethod === 'wechat' ? wechatInputRef.current?.click() : dingtalkInputRef.current?.click())}
            className={`
              relative w-13 h-13 rounded-[24px] flex items-center justify-center transition-all duration-700
              ${method === socialMethod ? 'text-white' : 'text-white/20 hover:text-white/60 hover:bg-white/5'}
            `}
          >
            {/* 社交项沿用同一套激活态视觉，保证交互一致性 */}
            {method === socialMethod && (
              <motion.div
                layoutId="activeLiquidTab"
                className="absolute inset-0 bg-white/[0.22] backdrop-blur-[100px] rounded-[24px] border border-white/70 shadow-[inset_0_0_35px_rgba(255,255,255,0.35),0_30px_60px_rgba(0,0,0,0.6)]"
                transition={{
                  type: 'spring',
                  stiffness: 120,
                  damping: 14,
                  mass: 2.2,
                }}
              >
                <div className="absolute inset-0 rounded-[24px] border-t border-white/90 opacity-95" />
                <div className="absolute inset-0 rounded-[24px] bg-gradient-to-b from-white/40 to-transparent opacity-70" />
              </motion.div>
            )}

            <motion.div
              className="relative z-10 w-6 h-6 flex items-center justify-center overflow-hidden rounded-lg"
              animate={{
                scale: method === socialMethod ? 1.25 : 1,
                rotate: method === socialMethod ? 0 : -10,
              }}
              transition={{ type: 'spring', stiffness: 300, damping: 15 }}
            >
              {socialMethod === 'wechat' ? (
                wechatIconUrl ? (
                  <img src={wechatIconUrl} alt="WeChat" className="w-full h-full object-cover" referrerPolicy="no-referrer" />
                ) : (
                  <MessageCircle className="w-6 h-6 text-[#07C160]" />
                )
              ) : dingtalkIconUrl ? (
                <img src={dingtalkIconUrl} alt="DingTalk" className="w-full h-full object-cover" referrerPolicy="no-referrer" />
              ) : (
                <Send className="w-6 h-6 text-[#0089FF]" />
              )}
            </motion.div>

            {/* 社交提示包含“可双击更换图标”的二级说明 */}
            <div
              className={`absolute left-full ml-6 px-5 py-3 bg-[#0d111c]/95 backdrop-blur-3xl rounded-2xl border border-white/25 text-[11px] font-bold text-white transition-all duration-300 pointer-events-none whitespace-nowrap z-50 shadow-[0_30px_60px_rgba(0,0,0,0.7)] ${
                hoveredMethod === socialMethod ? 'opacity-100 ml-8' : 'opacity-0'
              }`}
            >
              <div className="flex items-center gap-3.5">
                <div
                  className={`w-2 h-2 rounded-full shadow-[0_0_12px_rgba(255,255,255,1)] ${socialMethod === 'wechat' ? 'bg-[#07C160]' : 'bg-[#0089FF]'}`}
                />
                <div className="flex flex-col">
                  <span>{socialMethod === 'wechat' ? '微信登录' : '钉钉登录'}</span>
                  <span className="text-[8px] opacity-40 uppercase tracking-tighter">双击更换图标</span>
                </div>
              </div>
            </div>
          </button>
          {/* 隐藏上传控件：仅在双击时触发 */}
          <input
            ref={socialMethod === 'wechat' ? wechatInputRef : dingtalkInputRef}
            type="file"
            className="hidden"
            accept="image/*"
            onChange={(event) => onSocialIconUpload(event, socialMethod)}
          />
        </div>
      ))}
    </div>
  );
}
