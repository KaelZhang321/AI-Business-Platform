import { AnimatePresence, motion } from 'motion/react';

// 权限申请弹窗参数：
// - isOpen: 是否显示弹窗
// - onClose: 关闭弹窗回调（由父组件管理状态）
interface PermissionModalProps {
  isOpen: boolean;
  onClose: () => void;
}

// 权限申请弹窗：
// 该组件仅负责展示和关闭交互，表单提交逻辑可在后续接入真实接口时补充。
export function PermissionModal({ isOpen, onClose }: PermissionModalProps) {
  return (
    <AnimatePresence>
      {isOpen && (
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
            {/* 表单内容当前为占位字段，保持与旧页面视觉一致 */}
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
                <label htmlFor="leaderAgree" className="text-sm text-white/70">
                  部门领导已同意
                </label>
              </div>
              <div className="flex gap-4 mt-8">
                <button onClick={onClose} className="flex-1 py-3 rounded-xl font-bold text-white/60 hover:text-white transition-colors">
                  取消
                </button>
                <button onClick={onClose} className="flex-1 py-3 rounded-xl font-bold text-white bg-blue-600 hover:bg-blue-700 transition-all">
                  提交申请
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
