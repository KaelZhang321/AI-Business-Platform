/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// 登录页主文件：保留原有视觉效果，并接入真实账号密码登录逻辑。
import React, { useState, useEffect } from 'react';
import { 
  Eye, 
  EyeOff, 
  ShieldCheck, 
  Smartphone, 
  QrCode, 
  User,
  Mail,
  ArrowRight,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  RefreshCw,
  MessageCircle,
  Send
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

// --- Font Import ---
const FontLoader = () => (
  <style dangerouslySetInnerHTML={{ __html: `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  ` }} />
);

// --- Types ---
type LoginMethod = 'account' | 'mobile' | 'qrcode' | 'wechat' | 'dingtalk';

interface LoginCredentials {
  username: string;
  password: string;
}

interface LoginPageProps {
  onLogin: (credentials: LoginCredentials) => Promise<void>;
}

// --- Components ---

const InputField = ({ 
  label, 
  type = 'text', 
  placeholder, 
  value, 
  onChange, 
  error,
  icon: Icon,
  rightElement
}: {
  label: string;
  type?: string;
  placeholder?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  error?: string;
  icon?: any;
  rightElement?: React.ReactNode;
}) => {
  const [isFocused, setIsFocused] = useState(false);

  return (
    <div className="space-y-2 w-full group/field">
      <div className="flex justify-between items-end px-1">
        <label className="text-[10px] font-bold text-white/30 uppercase tracking-[0.25em] transition-colors">{label}</label>
      </div>
      <div className={`
        relative flex items-center transition-all duration-500 rounded-2xl border
        ${isFocused ? 'border-white/10 bg-white/[0.12]' : 'border-white/10 bg-white/[0.03]'}
        ${error ? 'border-red-500/50 ring-4 ring-red-500/5' : ''}
      `}>
        {Icon && <Icon className={`absolute left-4 w-4 h-4 transition-colors duration-500 ${isFocused ? 'text-white' : 'text-white/20'}`} />}
        <input
          type={type}
          className={`
            w-full py-3 px-4 outline-none focus:outline-none focus:ring-0 text-white placeholder:text-white/10 bg-transparent text-sm font-medium
            ${Icon ? 'pl-11' : ''}
            ${rightElement ? 'pr-11' : ''}
          `}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
        />
        {rightElement && (
          <div className="absolute right-3 flex items-center">
            {rightElement}
          </div>
        )}
      </div>
      <AnimatePresence>
        {error && (
          <motion.p 
            initial={{ opacity: 0, y: -5, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -5, filter: "blur(4px)" }}
            className="text-[9px] text-red-400/80 flex items-center gap-1.5 ml-1 font-bold tracking-wide"
          >
            <AlertCircle className="w-2.5 h-2.5" /> {error}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
};

const NeuralFlowBackground = () => {
  const nodeCount = 40;
  const width = 1000;
  const height = 1000;

  // Generate random nodes
  const nodes = React.useMemo(() => {
    return [...Array(nodeCount)].map((_, i) => ({
      id: i,
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 3 + 1,
      color: Math.random() > 0.5 ? "#06b6d4" : "#ffffff",
      delay: Math.random() * 5,
      speed: Math.random() * 2 + 1,
    }));
  }, []);

  // Generate flowing paths
  const paths = React.useMemo(() => {
    return [...Array(18)].map((_, i) => {
      const startX = Math.random() * width;
      const startY = Math.random() * height;
      
      // Create a sequence of points that flow in a general direction for smoother movement
      const angle = Math.random() * Math.PI * 2;
      const points = [{ x: startX, y: startY }];
      
      for (let j = 1; j < 6; j++) {
        const prev = points[j - 1];
        const dist = 150 + Math.random() * 100;
        // Keep the angle variation small to ensure smooth, rounded turns
        const currentAngle = angle + (Math.random() - 0.5) * 1.0; 
        points.push({
          x: prev.x + Math.cos(currentAngle) * dist,
          y: prev.y + Math.sin(currentAngle) * dist,
        });
      }

      // Construct a smooth path using Quadratic Beziers with midpoints for fluid transitions
      let d = `M ${points[0].x} ${points[0].y}`;
      for (let j = 1; j < points.length - 1; j++) {
        const xc = (points[j].x + points[j + 1].x) / 2;
        const yc = (points[j].y + points[j + 1].y) / 2;
        d += ` Q ${points[j].x} ${points[j].y} ${xc} ${yc}`;
      }
      // Final segment to the last point
      d += ` L ${points[points.length - 1].x} ${points[points.length - 1].y}`;

      return {
        id: i,
        d,
        color: Math.random() > 0.6 ? "#ec4899" : "#3b82f6",
        delay: Math.random() * 5,
        duration: Math.random() * 6 + 6,
      };
    });
  }, []);

  return (
    <div className="absolute inset-0 opacity-70 pointer-events-none overflow-hidden">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full" preserveAspectRatio="xMidYMid slice">
        {/* Flowing Fibers */}
        {paths.map((path) => (
          <React.Fragment key={path.id}>
            {/* Background static-ish fiber */}
            <motion.path
              d={path.d}
              fill="none"
              stroke={path.color}
              strokeWidth="0.4"
              strokeLinecap="round"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ 
                pathLength: [0, 1, 1, 0],
                opacity: [0, 0.15, 0.15, 0],
              }}
              transition={{
                duration: path.duration * 1.5,
                repeat: Infinity,
                ease: "easeInOut",
                delay: path.delay,
              }}
              className="blur-[0.5px]"
            />
            {/* Flowing light pulse */}
            <motion.path
              d={path.d}
              fill="none"
              stroke={path.color}
              strokeWidth="0.8"
              strokeLinecap="round"
              initial={{ pathLength: 0.1, pathOffset: 0, opacity: 0 }}
              animate={{ 
                pathOffset: [0, 1],
                opacity: [0, 0.8, 0],
              }}
              transition={{
                duration: path.duration,
                repeat: Infinity,
                ease: "linear",
                delay: path.delay,
              }}
              className="blur-[1px]"
              style={{
                filter: `drop-shadow(0 0 3px ${path.color})`
              }}
            />
          </React.Fragment>
        ))}

        {/* Glowing Nodes */}
        {nodes.map((node) => {
          const progress = node.y / height;
          const distFromMiddle = Math.abs(progress - 0.5) * 2;
          const baseOpacity = 0.05 + Math.pow(distFromMiddle, 2) * 0.7;

          return (
            <g key={node.id}>
              <motion.circle
                cx={node.x}
                cy={node.y}
                r={node.size * 2}
                fill={node.color}
                initial={{ opacity: 0 }}
                animate={{ 
                  opacity: [baseOpacity * 0.5, baseOpacity, baseOpacity * 0.5],
                  scale: [1, 1.5, 1],
                  x: [0, (Math.random() - 0.5) * 50, 0],
                  y: [0, (Math.random() - 0.5) * 50, 0],
                }}
                transition={{
                  duration: 10 + node.speed,
                  repeat: Infinity,
                  ease: "easeInOut",
                  delay: node.delay,
                }}
                className="blur-[2px]"
              />
              <motion.circle
                cx={node.x}
                cy={node.y}
                r={node.size}
                fill="#ffffff"
                initial={{ opacity: 0 }}
                animate={{ 
                  opacity: [baseOpacity, baseOpacity * 1.5, baseOpacity],
                  scale: [1, 1.2, 1],
                }}
                transition={{
                  duration: 5,
                  repeat: Infinity,
                  ease: "easeInOut",
                  delay: node.delay,
                }}
              />
            </g>
          );
        })}

        {/* Diagonal Light Streaks */}
        {[...Array(8)].map((_, i) => (
          <motion.line
            key={i}
            x1="-10%"
            y1={i * 15 + "%"}
            x2="110%"
            y2={i * 15 + 20 + "%"}
            stroke={i % 2 === 0 ? "#ec4899" : "#06b6d4"}
            strokeWidth="0.5"
            initial={{ opacity: 0 }}
            animate={{ 
              opacity: [0, 0.1, 0],
              strokeDashoffset: [200, 0]
            }}
            strokeDasharray="100 200"
            transition={{
              duration: 15 + i,
              repeat: Infinity,
              ease: "linear",
              delay: i * 2,
            }}
          />
        ))}
      </svg>
    </div>
  );
};

const PhotonParticles = () => {
  return (
    <div className="absolute inset-0 pointer-events-none">
      {[...Array(40)].map((_, i) => {
        const initialX = Math.random() * 100;
        const initialY = Math.random() * 100;
        const color = Math.random() > 0.5 ? "#06b6d4" : "#ec4899";
        
        return (
          <motion.div
            key={i}
            className="absolute w-1 h-1 rounded-full blur-[1px]"
            style={{ backgroundColor: color }}
            initial={{ 
              x: initialX + "%", 
              y: initialY + "%",
              opacity: 0 
            }}
            animate={{ 
              y: [null, "-100%"],
              opacity: [0, 0.4, 0],
              scale: [0, 1.2, 0]
            }}
            transition={{ 
              duration: Math.random() * 10 + 15, 
              repeat: Infinity, 
              ease: "linear",
              delay: Math.random() * 20
            }}
          />
        );
      })}
      {/* Global mask to fade middle content of background - More pronounced for login card */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,transparent_10%,rgba(1,1,7,0.7)_85%)]"></div>
    </div>
  );
};

export function LoginPage({ onLogin }: LoginPageProps) {
  const [method, setMethod] = useState<LoginMethod>('account');

  const handleSocialLogin = (m: 'wechat' | 'dingtalk') => {
    setMethod(m);
  };
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [captcha, setCaptcha] = useState('');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isCodeLoading, setIsCodeLoading] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isClicking, setIsClicking] = useState(false);
  const [isPermissionModalOpen, setIsPermissionModalOpen] = useState(false);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [wechatIconUrl, setWechatIconUrl] = useState<string | null>(null);
  const [dingtalkIconUrl, setDingtalkIconUrl] = useState<string | null>(null);
  const [hoveredMethod, setHoveredMethod] = useState<LoginMethod | null>(null);

  useEffect(() => {
    // 仅恢复“记住的账号”，不再像旧逻辑那样直接自动登录，避免绕过真实鉴权。
    const savedEmail = localStorage.getItem('rememberedEmail');
    if (savedEmail) {
      setEmail(savedEmail);
      setRememberMe(true);
    }
  }, []);

  useEffect(() => {
    let timer: number;
    if (countdown > 0) {
      timer = window.setTimeout(() => setCountdown(countdown - 1), 1000);
    }
    return () => window.clearTimeout(timer);
  }, [countdown]);

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  const handleMouseDown = () => setIsClicking(true);
  const handleMouseUp = () => setIsClicking(false);

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const url = URL.createObjectURL(file);
      setLogoUrl(url);
    }
  };

  const handleSocialIconUpload = (e: React.ChangeEvent<HTMLInputElement>, type: 'wechat' | 'dingtalk') => {
    const file = e.target.files?.[0];
    if (file) {
      const url = URL.createObjectURL(file);
      if (type === 'wechat') setWechatIconUrl(url);
      else setDingtalkIconUrl(url);
    }
  };

  const handleGetCode = async () => {
    if (!phone) {
      setErrors({ ...errors, phone: '请输入手机号或邮箱' });
      return;
    }
    setErrors({ ...errors, phone: '' });
    setIsCodeLoading(true);
    // 当前项目暂未接入短信/邮箱验证码接口，这里先保留占位行为。
    await new Promise(resolve => setTimeout(resolve, 1000));
    setIsCodeLoading(false);
    setCountdown(60);
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    const newErrors: { [key: string]: string } = {};
    
    if (method === 'account') {
      if (!email) newErrors.email = '请输入工号或邮箱';
      if (!password) newErrors.password = '请输入密码';
      if (!captcha) newErrors.captcha = '请输入验证码';
    } else if (method === 'mobile') {
      if (!phone) newErrors.phone = '请输入手机号或邮箱';
      if (!code) newErrors.code = '请输入验证码';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});
    setIsLoading(true);

    try {
      if (method === 'account') {
        // 账号密码登录已经接入真实后端接口。
        await onLogin({
          username: email,
          password,
        });

        if (rememberMe) {
          localStorage.setItem('rememberedEmail', email);
        } else {
          localStorage.removeItem('rememberedEmail');
        }
      } else {
        // 其余登录方式暂未融合真实后端，所以在界面上给出明确提示。
        setErrors({ general: '当前页面暂未接入该登录方式，请使用账号密码登录。' });
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '登录失败，请检查账号、密码或接口配置。';
      setErrors({ general: message });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div 
      className="min-h-screen w-full bg-[#010107] flex items-center justify-center p-4 font-sans selection:bg-blue-500/30 selection:text-white overflow-hidden relative"
      onMouseMove={handleMouseMove}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
    >
      <FontLoader />
      {/* Click Ripple Effect - Global */}
      <AnimatePresence>
        {isClicking && (
          <motion.div
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 0.3, scale: 1.2 }}
            exit={{ opacity: 0, scale: 1.5 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
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
      
      {/* Background Atmosphere - Future Medical AI Theme */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden bg-[#010107]">
        {/* Deep Space Base */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,#0a192f_0%,#010107_100%)]"></div>
        
        {/* Neural Flow Background */}
        <NeuralFlowBackground />

        {/* Photon Particles */}
        <PhotonParticles />

        {/* Planet/Horizon Glow - Medical Cyan/Blue/Magenta */}
        <div className="absolute bottom-[-40%] left-[-10%] right-[-10%] h-[80%] bg-[radial-gradient(ellipse_at_bottom,rgba(236,72,153,0.15)_0%,rgba(59,130,246,0.05)_50%,transparent_100%)] rounded-[100%] blur-[120px]"></div>
        
        {/* Tech Grid Pattern */}
        <div className="absolute inset-0 opacity-[0.05] bg-[linear-gradient(to_right,#3b82f6_1px,transparent_1px),linear-gradient(to_bottom,#3b82f6_1px,transparent_1px)] bg-[size:80px_80px]"></div>
        
        {/* Scanning Line Effect */}
        <motion.div 
          animate={{ y: ["0%", "100%", "0%"] }}
          transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
          className="absolute inset-0 w-full h-[2px] bg-gradient-to-r from-transparent via-cyan-400/20 to-transparent blur-[2px]"
        />

        {/* Top Glow */}
        <div className="absolute top-[-20%] left-[20%] w-[60%] h-[40%] bg-blue-500/10 blur-[100px] rounded-full"></div>

        {/* Floating Grain Texture */}
        <div className="absolute inset-0 opacity-[0.03] pointer-events-none mix-blend-overlay" style={{ backgroundImage: 'url("https://grainy-gradients.vercel.app/noise.svg")' }}></div>
      </div>

      <motion.div 
        initial={{ opacity: 0, scale: 0.98, y: 40 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 1.5, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10"
      >
        {/* Unified Login Card - Integrated Glass Rail */}
        <div className="relative group">
          {/* Reference Image Style: Atmospheric Glows */}
          {/* Dynamic Flowing Highlight Layer - Refined */}
          <motion.div 
            animate={{ opacity: [0.1, 0.4, 0.1] }}
            transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
            className="absolute -inset-[15px] rounded-[55px] blur-[20px] pointer-events-none"
            style={{
              background: "radial-gradient(circle at 0% 0%, rgba(34,211,238,0.5) 0%, transparent 40%), radial-gradient(circle at 100% 100%, rgba(34,211,238,0.5) 0%, transparent 40%)"
            }}
          />
          
          {/* Outer refraction glow - Multi-layered for depth */}
          <motion.div 
            animate={{ 
              opacity: [0.4, 0.8, 0.4],
              filter: [
                "drop-shadow(0 0 4px rgba(34,211,238,0.3))",
                "drop-shadow(0 0 16px rgba(34,211,238,0.6))",
                "drop-shadow(0 0 4px rgba(34,211,238,0.3))"
              ]
            }}
            transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
            className="absolute -inset-[1px] rounded-[41px] pointer-events-none p-[1px]"
            style={{
              background: "linear-gradient(135deg, rgba(34,211,238,1) 0%, rgba(34,211,238,0) 50%, rgba(34,211,238,1) 100%)",
              WebkitMask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
              WebkitMaskComposite: "xor",
              maskComposite: "exclude",
            }}
          ></motion.div>
          
          <div className="flex relative rounded-[40px] shadow-[0_120px_240px_-60px_rgba(0,0,0,1),inset_0_0_0_1.5px_rgba(255,255,255,0.05)] bg-[#0d111c]/30 backdrop-blur-[120px]">
            {/* Glass Background & Effects Wrapper - No overflow-hidden on parent to allow tooltips to pop out */}
            <div className="absolute inset-0 bg-[#0d111c]/5 backdrop-blur-[120px] rounded-[40px] overflow-hidden pointer-events-none z-0">
              {/* Frosted Grain Overlay on Card */}
              <div className="absolute inset-0 opacity-[0.04] pointer-events-none mix-blend-overlay" style={{ backgroundImage: 'url("https://grainy-gradients.vercel.app/noise.svg")' }}></div>
              
              {/* Glass Reflection Overlay - Animated */}
              <motion.div 
                animate={{ x: ['-200%', '200%'] }}
                transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }}
                className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.08] to-transparent pointer-events-none skew-x-[-35deg]"
              />
              
              {/* Rail Background Clipping Area */}
              <div className="absolute top-0 bottom-0 right-0 w-20 bg-white/[0.01] border-l border-white/[0.1]"></div>
            </div>
            
            {/* Left Content Area */}
            <div className="w-[500px] p-10 pt-8 relative z-10">
              <div className="flex items-center justify-between mb-8">
                <label className="flex items-center cursor-pointer group/workspace-upload relative p-2 -m-2 rounded-2xl transition-all duration-300 min-h-[64px]">
                  <input type="file" className="hidden" accept="image/*" onChange={handleLogoUpload} />
                  
                  <AnimatePresence mode="wait">
                    {logoUrl ? (
                      <motion.div 
                        key="uploaded-logo"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        className="relative h-14 flex items-center"
                      >
                        <img 
                          src={logoUrl} 
                          alt="Workspace Logo" 
                          className="h-full w-auto max-w-[240px] object-contain rounded-lg shadow-[0_10px_30px_rgba(0,0,0,0.3)]" 
                          referrerPolicy="no-referrer" 
                        />
                      </motion.div>
                    ) : (
                      <motion.div 
                        key="placeholder"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="flex items-center gap-4"
                      >
                        {/* Integrated Logo Icon */}
                        <div className="w-14 h-14 bg-gradient-to-br from-blue-600 to-blue-800 rounded-[22px] flex items-center justify-center shadow-[0_15px_40px_rgba(37,99,235,0.4)] border border-white/30 relative overflow-hidden transition-all duration-500">
                          <div className="absolute inset-0 bg-gradient-to-tr from-white/40 to-transparent opacity-0 transition-opacity duration-500"></div>
                          <div className="flex flex-col items-center">
                            <Sparkles className="text-white w-6 h-6 relative z-10" />
                            <span className="text-[7px] text-white/60 font-bold uppercase tracking-tighter mt-0.5">AI</span>
                          </div>
                        </div>

                        {/* Integrated Text Info */}
                        <div className="flex flex-col">
                          <h2 className="text-base font-bold text-white tracking-tight leading-tight transition-colors flex items-center gap-2">
                            AI 业务工作台
                          </h2>
                          <p className="text-[10px] text-white/40 uppercase tracking-[0.4em] font-bold mt-1 transition-colors">点击上传企业 Logo</p>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </label>
                <div className="flex items-center gap-2.5 px-3.5 py-1.5 bg-white/[0.08] rounded-full border border-white/15 backdrop-blur-2xl">
                  <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_15px_rgba(34,197,94,1)] animate-pulse"></div>
                  <span className="text-[10px] text-white/70 font-bold uppercase tracking-widest">Active</span>
                </div>
              </div>

              <div className="relative h-[380px]">
                <AnimatePresence mode="wait" initial={false}>
                  {method === 'account' && (
                    <motion.form 
                      key="account"
                      initial={{ opacity: 0, x: 40, scale: 0.92, filter: "blur(40px)" }}
                      animate={{ opacity: 1, x: 0, scale: 1, filter: "blur(0px)" }}
                      exit={{ opacity: 0, x: -40, scale: 1.08, filter: "blur(40px)" }}
                      transition={{ duration: 1.2, ease: [0.19, 1, 0.22, 1] }}
                      onSubmit={handleLogin} 
                      className="space-y-4 absolute inset-0"
                    >
                      <InputField
                        label="Employee ID"
                        placeholder="工号或企业邮箱"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        error={errors.email}
                        icon={User}
                      />
                      <InputField
                        label="Password"
                        type={showPassword ? 'text' : 'password'}
                        placeholder="内网登录密码"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        error={errors.password}
                        icon={ShieldCheck}
                        rightElement={
                          <button type="button" onClick={() => setShowPassword(!showPassword)} className="text-white/20 hover:text-white/60 transition-colors">
                            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        }
                      />
                      <div className="flex gap-4 items-end">
                        <InputField
                          label="Captcha"
                          placeholder="验证码"
                          value={captcha}
                          onChange={(e) => setCaptcha(e.target.value)}
                          error={errors.captcha}
                        />
                        <div className="w-32 h-[48px] bg-white/[0.05] rounded-2xl flex items-center justify-center cursor-pointer border border-white/15 text-blue-300 font-mono font-bold tracking-[0.2em] text-sm transition-all group/captcha shadow-inner">
                          <span>4X9K</span>
                        </div>
                      </div>

                      {errors.general ? (
                        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs font-medium text-red-200">
                          {errors.general}
                        </div>
                      ) : null}
                      
                      <div className="flex items-center justify-between px-1 pt-2">
                        <label className="flex items-center gap-3 cursor-pointer group/check">
                          <div className={`w-5 h-5 rounded-lg border flex items-center justify-center transition-all duration-500 ${rememberMe ? 'bg-blue-500 border-blue-500 shadow-[0_0_20px_rgba(59,130,246,0.7)]' : 'border-white/20'}`}>
                            <input type="checkbox" className="hidden" checked={rememberMe} onChange={() => setRememberMe(!rememberMe)} />
                            {rememberMe && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
                          </div>
                          <span className="text-[11px] text-white/50 select-none transition-colors font-semibold">保持登录状态</span>
                        </label>
                        <button type="button" className="text-[11px] font-bold text-blue-400/60 transition-colors">忘记密码？</button>
                      </div>

                      <button 
                        type="submit" 
                        disabled={isLoading} 
                        className="w-full py-4 rounded-full font-bold text-white bg-gradient-to-r from-blue-500 to-blue-600 shadow-[0_25px_50px_rgba(59,130,246,0.4)] active:scale-[0.98] transition-all flex items-center justify-center gap-2.5 text-sm mt-4 border border-white/20"
                      >
                        {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : '进入系统'}
                      </button>
                    </motion.form>
                  )}

                  {method === 'mobile' && (
                    <motion.form 
                      key="mobile"
                      initial={{ opacity: 0, x: 40, scale: 0.92, filter: "blur(40px)" }}
                      animate={{ opacity: 1, x: 0, scale: 1, filter: "blur(0px)" }}
                      exit={{ opacity: 0, x: -40, scale: 1.08, filter: "blur(40px)" }}
                      transition={{ duration: 1.2, ease: [0.19, 1, 0.22, 1] }}
                      onSubmit={handleLogin} 
                      className="space-y-4 absolute inset-0"
                    >
                      <InputField
                        label="Phone / Email"
                        placeholder="请输入手机号或邮箱"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        error={errors.phone}
                        icon={Smartphone}
                      />
                      <div className="flex gap-4 items-end">
                        <InputField
                          label="Verification Code"
                          placeholder="验证码"
                          value={code}
                          onChange={(e) => setCode(e.target.value)}
                          error={errors.code}
                        />
                        <button 
                          type="button" 
                          onClick={handleGetCode}
                          disabled={isCodeLoading || countdown > 0}
                          className="w-32 h-[48px] bg-white/[0.05] rounded-2xl flex items-center justify-center border border-white/15 text-blue-400 text-[11px] font-bold hover:bg-white/[0.12] transition-all shadow-inner disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {isCodeLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : countdown > 0 ? `${countdown}s 后重新获取` : '获取验证码'}
                        </button>
                      </div>
                      
                      <div className="h-16"></div>

                      <button 
                        type="submit" 
                        disabled={isLoading} 
                        className="w-full py-4 rounded-full font-bold text-white bg-gradient-to-r from-blue-500 to-blue-600 shadow-[0_25px_50px_rgba(59,130,246,0.4)] active:scale-[0.98] transition-all flex items-center justify-center gap-2.5 text-sm border border-white/20"
                      >
                        {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : '验证并登录'}
                      </button>
                    </motion.form>
                  )}

                  {method === 'qrcode' && (
                    <motion.div 
                      key="qrcode"
                      initial={{ opacity: 0, x: 40, scale: 0.92, filter: "blur(40px)" }}
                      animate={{ opacity: 1, x: 0, scale: 1, filter: "blur(0px)" }}
                      exit={{ opacity: 0, x: -40, scale: 1.08, filter: "blur(40px)" }}
                      transition={{ duration: 1.2, ease: [0.19, 1, 0.22, 1] }}
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

                  {method === 'wechat' && (
                    <motion.div 
                      key="wechat"
                      initial={{ opacity: 0, x: 40, scale: 0.92, filter: "blur(40px)" }}
                      animate={{ opacity: 1, x: 0, scale: 1, filter: "blur(0px)" }}
                      exit={{ opacity: 0, x: -40, scale: 1.08, filter: "blur(40px)" }}
                      transition={{ duration: 1.2, ease: [0.19, 1, 0.22, 1] }}
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

                  {method === 'dingtalk' && (
                    <motion.div 
                      key="dingtalk"
                      initial={{ opacity: 0, x: 40, scale: 0.92, filter: "blur(40px)" }}
                      animate={{ opacity: 1, x: 0, scale: 1, filter: "blur(0px)" }}
                      exit={{ opacity: 0, x: -40, scale: 1.08, filter: "blur(40px)" }}
                      transition={{ duration: 1.2, ease: [0.19, 1, 0.22, 1] }}
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

              <div className="mt-8 pt-8 border-t border-white/[0.1] flex justify-between items-center">
                <p className="text-[11px] text-white/40">
                  新员工？ <button className="font-bold text-blue-400/70 transition-colors">联系 IT</button>
                </p>
                <button 
                  onClick={() => setIsPermissionModalOpen(true)}
                  className="text-[11px] font-bold text-blue-400/70 transition-colors"
                >
                  权限申请
                </button>
              </div>
            </div>

            {/* 权限申请模态框 */}
            <AnimatePresence>
              {isPermissionModalOpen && (
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
                >
                  <motion.div 
                    initial={{ scale: 0.95, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0.95, opacity: 0 }}
                    className="bg-[#0d111c] border border-white/10 p-8 rounded-[40px] w-full max-w-md shadow-2xl"
                  >
                    <h2 className="text-xl font-bold text-white mb-6">权限申请表单</h2>
                    <div className="space-y-4">
                      <div>
                        <label className="block text-xs font-bold text-white/50 mb-2">姓名</label>
                        <input className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-white text-sm" placeholder="请输入姓名" />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-white/50 mb-2">手机号码</label>
                        <input className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-white text-sm" placeholder="请输入手机号码" />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-white/50 mb-2">部门</label>
                        <select className="w-full bg-[#0d111c] border border-white/10 rounded-xl p-3 text-white text-sm">
                          <option>请选择部门</option>
                          <option>IT部</option>
                          <option>预约部</option>
                          <option>运营部</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-white/50 mb-2">申请权限范围</label>
                        <select className="w-full bg-[#0d111c] border border-white/10 rounded-xl p-3 text-white text-sm">
                          <option>请选择权限范围</option>
                          <option>预约中台</option>
                          <option>360系统</option>
                          <option>CRM</option>
                        </select>
                      </div>
                      <div className="flex items-center gap-3">
                        <input type="checkbox" id="leaderAgree" className="w-4 h-4 rounded border-white/10 bg-white/5" />
                        <label htmlFor="leaderAgree" className="text-sm text-white/70">部门领导已同意</label>
                      </div>
                      <div className="flex gap-4 mt-8">
                        <button 
                          onClick={() => setIsPermissionModalOpen(false)}
                          className="flex-1 py-3 rounded-xl font-bold text-white/60 hover:text-white transition-colors"
                        >
                          取消
                        </button>
                        <button 
                          onClick={() => setIsPermissionModalOpen(false)}
                          className="flex-1 py-3 rounded-xl font-bold text-white bg-blue-600 hover:bg-blue-700 transition-all"
                        >
                          提交申请
                        </button>
                      </div>
                    </div>
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Integrated Vertical Switcher Rail - Refined Apple Style */}
            <div className="w-20 flex flex-col items-center py-10 gap-4 relative z-10">
              <div className="absolute top-0 bottom-0 left-0 w-[1px] bg-gradient-to-b from-transparent via-white/40 to-transparent"></div>
              
              {(['account', 'mobile', 'qrcode'] as LoginMethod[]).map((m) => (
                <button
                  key={m}
                  onClick={() => setMethod(m)}
                  onMouseEnter={() => setHoveredMethod(m)}
                  onMouseLeave={() => setHoveredMethod(null)}
                  className={`
                    relative w-13 h-13 rounded-[24px] flex items-center justify-center transition-all duration-700 group
                    ${method === m ? 'text-white' : 'text-white/20 hover:text-white/60 hover:bg-white/5'}
                  `}
                >
                  {method === m && (
                    <motion.div
                      layoutId="activeLiquidTab"
                      className="absolute inset-0 bg-white/[0.22] backdrop-blur-[100px] rounded-[24px] border border-white/70 shadow-[inset_0_0_35px_rgba(255,255,255,0.35),0_30px_60px_rgba(0,0,0,0.6)]"
                      transition={{ 
                        type: "spring", 
                        stiffness: 120, 
                        damping: 14,
                        mass: 2.2
                      }}
                    >
                      {/* Silky Refraction Edge */}
                      <div className="absolute inset-0 rounded-[24px] border-t border-white/90 opacity-95"></div>
                      <div className="absolute inset-0 rounded-[24px] bg-gradient-to-b from-white/40 to-transparent opacity-70"></div>
                    </motion.div>
                  )}
                  
                  <motion.div 
                    className="relative z-10"
                    animate={{ 
                      scale: method === m ? 1.25 : 1,
                      rotate: method === m ? 0 : -10
                    }}
                    transition={{ type: "spring", stiffness: 300, damping: 15 }}
                  >
                    {m === 'account' && <User className="w-6 h-6" />}
                    {m === 'mobile' && <Smartphone className="w-6 h-6" />}
                    {m === 'qrcode' && <QrCode className="w-6 h-6" />}
                  </motion.div>

                  {/* Tooltip - Apple Style Refined */}
                  <div className={`absolute left-full ml-6 px-5 py-3 bg-[#0d111c]/95 backdrop-blur-3xl rounded-2xl border border-white/25 text-[11px] font-bold text-white transition-all duration-300 pointer-events-none whitespace-nowrap z-50 shadow-[0_30px_60px_rgba(0,0,0,0.7)] ${hoveredMethod === m ? 'opacity-100 ml-8' : 'opacity-0'}`}>
                    <div className="flex items-center gap-3.5">
                      <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_12px_rgba(59,130,246,1)]"></div>
                      {m === 'account' ? '账号登录' : m === 'mobile' ? '手机登录' : '扫码登录'}
                    </div>
                  </div>
                </button>
              ))}

              {/* Spacer to push social icons down */}
              <div className="flex-grow" />

              {/* Separator */}
              <div className="w-8 h-[1px] bg-white/10 my-2" />

              {(['wechat', 'dingtalk'] as LoginMethod[]).map((m) => (
                <div key={m} className="relative group">
                  <button
                    onClick={() => setMethod(m)}
                    onMouseEnter={() => setHoveredMethod(m)}
                    onMouseLeave={() => setHoveredMethod(null)}
                    onDoubleClick={() => {
                      const input = document.getElementById(`upload-${m}`);
                      input?.click();
                    }}
                    className={`
                      relative w-13 h-13 rounded-[24px] flex items-center justify-center transition-all duration-700
                      ${method === m ? 'text-white' : 'text-white/20 hover:text-white/60 hover:bg-white/5'}
                    `}
                  >
                    {method === m && (
                      <motion.div
                        layoutId="activeLiquidTab"
                        className="absolute inset-0 bg-white/[0.22] backdrop-blur-[100px] rounded-[24px] border border-white/70 shadow-[inset_0_0_35px_rgba(255,255,255,0.35),0_30px_60px_rgba(0,0,0,0.6)]"
                        transition={{ 
                          type: "spring", 
                          stiffness: 120, 
                          damping: 14,
                          mass: 2.2
                        }}
                      >
                        {/* Silky Refraction Edge */}
                        <div className="absolute inset-0 rounded-[24px] border-t border-white/90 opacity-95"></div>
                        <div className="absolute inset-0 rounded-[24px] bg-gradient-to-b from-white/40 to-transparent opacity-70"></div>
                      </motion.div>
                    )}
                    
                    <motion.div 
                      className="relative z-10 w-6 h-6 flex items-center justify-center overflow-hidden rounded-lg"
                      animate={{ 
                        scale: method === m ? 1.25 : 1,
                        rotate: method === m ? 0 : -10
                      }}
                      transition={{ type: "spring", stiffness: 300, damping: 15 }}
                    >
                      {m === 'wechat' ? (
                        wechatIconUrl ? (
                          <img src={wechatIconUrl} alt="WeChat" className="w-full h-full object-cover" referrerPolicy="no-referrer" />
                        ) : (
                          <MessageCircle className="w-6 h-6 text-[#07C160]" />
                        )
                      ) : (
                        dingtalkIconUrl ? (
                          <img src={dingtalkIconUrl} alt="DingTalk" className="w-full h-full object-cover" referrerPolicy="no-referrer" />
                        ) : (
                          <Send className="w-6 h-6 text-[#0089FF]" />
                        )
                      )}
                    </motion.div>

                    {/* Tooltip - Apple Style Refined */}
                    <div className={`absolute left-full ml-6 px-5 py-3 bg-[#0d111c]/95 backdrop-blur-3xl rounded-2xl border border-white/25 text-[11px] font-bold text-white transition-all duration-300 pointer-events-none whitespace-nowrap z-50 shadow-[0_30px_60px_rgba(0,0,0,0.7)] ${hoveredMethod === m ? 'opacity-100 ml-8' : 'opacity-0'}`}>
                      <div className="flex items-center gap-3.5">
                        <div className={`w-2 h-2 rounded-full shadow-[0_0_12px_rgba(255,255,255,1)] ${m === 'wechat' ? 'bg-[#07C160]' : 'bg-[#0089FF]'}`}></div>
                        <div className="flex flex-col">
                          <span>{m === 'wechat' ? '微信登录' : '钉钉登录'}</span>
                          <span className="text-[8px] opacity-40 uppercase tracking-tighter">双击更换图标</span>
                        </div>
                      </div>
                    </div>
                  </button>
                  <input 
                    id={`upload-${m}`}
                    type="file" 
                    className="hidden" 
                    accept="image/*" 
                    onChange={(e) => handleSocialIconUpload(e, m as 'wechat' | 'dingtalk')} 
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Footer */}
      <div className="fixed bottom-8 left-0 right-0 flex flex-col items-center gap-2 pointer-events-none opacity-20">
        <p className="text-[9px] uppercase tracking-[0.4em] text-white font-medium">
          © 2026 LIZHI ZHISHU TECHNOLOGY. SECURED BY AI.
        </p>
      </div>
    </div>
  );
}
