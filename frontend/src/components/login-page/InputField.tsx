import { AlertCircle, type LucideIcon } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useState, type ChangeEvent, type ReactNode } from 'react';

// 通用输入组件参数：
// - 保持“视觉壳 + 状态反馈”统一
// - 具体字段逻辑（校验/提交）由父组件负责
interface InputFieldProps {
  label: string;
  type?: string;
  placeholder?: string;
  value: string;
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
  error?: string;
  icon?: LucideIcon;
  rightElement?: ReactNode;
}

export function InputField({
  label,
  type = 'text',
  placeholder,
  value,
  onChange,
  error,
  icon: Icon,
  rightElement,
}: InputFieldProps) {
  // 仅用于视觉反馈（边框高亮、图标提亮），不承载业务状态。
  const [isFocused, setIsFocused] = useState(false);

  return (
    <div className="space-y-2 w-full group/field">
      <div className="flex justify-between items-end px-1">
        <label className="text-[10px] font-bold text-white/30 uppercase tracking-[0.25em] transition-colors">{label}</label>
      </div>
      {/* 聚焦时提升可读性；错误时额外叠加红色反馈样式。 */}
      <div
        className={`
        relative flex items-center transition-all duration-500 rounded-2xl border
        ${isFocused ? 'border-white/10 bg-white/[0.12]' : 'border-white/10 bg-white/[0.03]'}
        ${error ? 'border-red-500/50 ring-4 ring-red-500/5' : ''}
      `}
      >
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
        {rightElement && <div className="absolute right-3 flex items-center">{rightElement}</div>}
      </div>
      <AnimatePresence>
        {/* 错误文案使用入场/退场动画，避免表单抖动感 */}
        {error && (
          <motion.p
            initial={{ opacity: 0, y: -5, filter: 'blur(4px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            exit={{ opacity: 0, y: -5, filter: 'blur(4px)' }}
            className="text-[9px] text-red-400/80 flex items-center gap-1.5 ml-1 font-bold tracking-wide"
          >
            <AlertCircle className="w-2.5 h-2.5" /> {error}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}
