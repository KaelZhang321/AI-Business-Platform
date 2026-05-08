import React, { useState } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'motion/react';
import { Check, Pencil, Trash2 } from 'lucide-react';
import type { SavedLayout } from './types';

/** 可编辑布局标签组件属性 */
interface EditableLayoutTagProps {
  /** 布局数据 */
  layout: SavedLayout;
  /** 重命名回调 */
  onRename: (id: string, newName: string) => Promise<void> | void;
  /** 应用布局回调 */
  onApply: (id: string) => void;
  /** 删除布局回调 */
  onDelete: (id: string) => Promise<void> | void;
}

/** 可编辑布局标签组件：支持 3D 悬停效果、在线重命名、应用和删除布局 */
export const EditableLayoutTag: React.FC<EditableLayoutTagProps> = ({ layout, onRename, onApply, onDelete }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(layout.name);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const mouseXSpring = useSpring(x, { stiffness: 300, damping: 20 });
  const mouseYSpring = useSpring(y, { stiffness: 300, damping: 20 });

  const rotateX = useTransform(mouseYSpring, [-0.5, 0.5], ['15deg', '-15deg']);
  const rotateY = useTransform(mouseXSpring, [-0.5, 0.5], ['-15deg', '15deg']);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const xPct = mouseX / width - 0.5;
    const yPct = mouseY / height - 0.5;
    x.set(xPct);
    y.set(yPct);
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  const handleSave = async () => {
    if (isSaving) {
      return;
    }

    const targetName = name.trim();
    if (!targetName) {
      setName(layout.name);
      setIsEditing(false);
      return;
    }

    try {
      setIsSaving(true);
      await onRename(layout.id, targetName);
      setIsEditing(false);
      setName(targetName);
    } catch {
      setName(layout.name);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (isDeleting) {
      return;
    }

    try {
      setIsDeleting(true);
      await onDelete(layout.id);
    } finally {
      setIsDeleting(false);
    }
  };

  if (isEditing) {
    return (
      <div className="flex items-center space-x-1 rounded-xl border border-blue-300 bg-white px-3 py-1.5 dark:bg-slate-800">
        <input
          autoFocus
          disabled={isSaving}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => {
            void handleSave();
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              void handleSave();
            }
          }}
          className="w-24 bg-transparent text-xs text-slate-900 outline-none dark:text-white"
        />
        <button
          disabled={isSaving}
          onClick={() => {
            void handleSave();
          }}
          className="text-blue-500 hover:text-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Check className="h-3 w-3" />
        </button>
      </div>
    );
  }

  return (
    <motion.div
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        rotateX,
        rotateY,
        transformStyle: 'preserve-3d',
        perspective: 1000,
      }}
      className="group relative cursor-pointer rounded-2xl border border-white/60 bg-gradient-to-br from-blue-500/10 via-indigo-500/10 to-purple-500/10 px-5 py-2.5 text-sm font-semibold text-indigo-900 backdrop-blur-md transition-colors dark:border-white/10 dark:from-blue-500/20 dark:via-indigo-500/20 dark:to-purple-500/20 dark:text-indigo-100"
      title="点击应用布局"
    >
      <div style={{ transform: 'translateZ(30px)' }} className="relative z-10 flex items-center space-x-2">
        <span onClick={() => onApply(layout.id)} className="block drop-shadow-sm">
          {layout.name}
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            setIsEditing(true);
          }}
          className="ml-1 opacity-0 transition-opacity group-hover:opacity-100 text-indigo-400 hover:text-indigo-600 dark:text-indigo-300 dark:hover:text-indigo-100"
          title="修改名称"
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
        <button
          disabled={isDeleting}
          onClick={(e) => {
            void handleDelete(e);
          }}
          className="opacity-0 transition-opacity group-hover:opacity-100 text-rose-400 hover:text-rose-600 dark:text-rose-300 dark:hover:text-rose-100 disabled:opacity-40 disabled:cursor-not-allowed"
          title="删除布局"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </motion.div>
  );
};
