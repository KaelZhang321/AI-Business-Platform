// 路由占位页：为尚未接入真实业务逻辑的菜单提供统一的过渡界面。
import React from 'react';
import { Clock3, Sparkles } from 'lucide-react';

/** 占位页组件属性 */
interface PlaceholderPageProps {
  /** 页面标题 */
  title: string;
  /** 页面描述文案 */
  description: string;
}

/** 占位页组件：为尚未接入真实业务逻辑的菜单提供统一的过渡界面 */
export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <section className="relative overflow-hidden rounded-[32px] border border-slate-200/70 bg-white/80 px-8 py-10 shadow-sm dark:border-slate-700/70 dark:bg-slate-900/80">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(0,122,255,0.08),_transparent_35%),radial-gradient(circle_at_bottom_left,_rgba(16,185,129,0.08),_transparent_30%)]" />

      <div className="relative space-y-8">
        <div className="flex items-start justify-between gap-6">
          <div className="space-y-4">
            <div className="inline-flex items-center rounded-full border border-brand/10 bg-brand/5 px-3 py-1 text-xs font-semibold text-brand dark:border-brand/30 dark:bg-brand/15">
              页面建设中
            </div>
            <div className="space-y-2">
              <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">{title}</h2>
              <p className="max-w-3xl text-sm leading-7 text-slate-600 dark:text-slate-300">{description}</p>
            </div>
          </div>

          <div className="hidden rounded-3xl bg-slate-900 p-5 text-white shadow-xl dark:bg-slate-800 lg:block">
            <Sparkles className="h-8 w-8 text-brand-light" />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5 dark:border-slate-700 dark:bg-slate-800/70">
            <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-white shadow-sm dark:bg-slate-700">
              <Clock3 className="h-5 w-5 text-brand" />
            </div>
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">路由已接通</h3>
            <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">当前菜单已经具备独立路径，后续接业务接口时可以直接挂载到对应页面。</p>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5 dark:border-slate-700 dark:bg-slate-800/70">
            <div className="mb-3 text-sm font-semibold text-slate-900 dark:text-slate-100">建议下一步</div>
            <p className="text-sm leading-6 text-slate-500 dark:text-slate-400">优先补接口、鉴权和数据流，再把卡片区、列表区和详情抽屉逐步替换成真实业务组件。</p>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5 dark:border-slate-700 dark:bg-slate-800/70">
            <div className="mb-3 text-sm font-semibold text-slate-900 dark:text-slate-100">当前收益</div>
            <p className="text-sm leading-6 text-slate-500 dark:text-slate-400">即使页面尚未开发完成，导航状态、路径分享和后续拆分懒加载的基础已经准备好了。</p>
          </div>
        </div>
      </div>
    </section>
  );
}
