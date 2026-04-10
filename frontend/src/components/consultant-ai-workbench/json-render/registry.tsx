/**
 * registry.tsx — Standalone Mode 组件注册表
 *
 * 使用 @json-render/react 的 createRenderer API（Standalone Mode）：
 *
 * ┌─────────────────────────────────────────────────────────────────┐
 * │  Standalone Mode vs Provider Mode 对比                          │
 * │                                                                 │
 * │  Provider Mode（旧）：                                          │
 * │    defineRegistry → registry 对象                               │
 * │    <StateProvider>                                              │
 * │      <ActionProvider handlers={...}>                            │
 * │        <VisibilityProvider>                                     │
 * │          <ValidationProvider>                                   │
 * │            <Renderer registry={registry} spec={spec} />        │
 * │                                                                 │
 * │  Standalone Mode（新）：                                        │
 * │    createRenderer → <AssistantRenderer> 单个组件                │
 * │    <AssistantRenderer                                           │
 * │      spec={spec}                                                │
 * │      state={initialState}                                       │
 * │      onAction={(name, params) => { ... }}                       │
 * │    />                                                           │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * 优点：
 *   - 使用者无需手动嵌套 Provider，使用更简单
 *   - onAction 统一处理所有自定义动作，逻辑集中
 *   - 适合将整个渲染器作为"黑盒"在消息组件中复用
 *
 * 组件参数变化（createRenderer API）：
 *   - Provider Mode: ({ props, children, emit, bindings })
 *   - Standalone Mode: ({ element, children, emit, on, bindings })
 *     其中 props 通过 element.props 访问
 */
import { createRenderer, useBoundProp } from '@json-render/react';
import { useEffect, useState, useMemo } from 'react';
import { apiClient } from '../../../services/api';
import { assistantCatalog } from './catalog';
import { Table, Descriptions } from 'antd';

// ─── 字典选项类型 ────────────────────────────────────────────────────────────
interface DictOption {
  label: string; // 显示文字（对应后端 dictLabel 字段）
  value: string; // 选项值（对应后端 dictValue 字段）
}

/**
 * dictCache — 模块级字典缓存（按 dictCode 缓存每次接口响应）。
 *
 * 同一 dictCode 在整个页面生命周期内只请求一次接口。
 */
const dictCache = new Map<string, DictOption[]>();

/**
 * fetchDictOptions — 根据字典编码请求选项列表。
 *
 * 接口约定（可按实际后端格式调整）：
 *   GET /api/v1/system/dict/data/type/{dictCode}
 *   响应：{ data: Array<{ dictLabel: string, dictValue: string }> }
 *
 * 如果你的接口路径或字段名不同，只需修改这一个函数，组件代码无需改动。
 */
async function fetchDictOptions(dictCode: string): Promise<DictOption[]> {
  if (dictCache.has(dictCode)) {
    return dictCache.get(dictCode)!;
  }
  try {
    const res = await apiClient.get<{
      data: Array<{ dictLabel: string; dictValue: string }>;
    }>(`/api/v1/system/dict/data/type/${dictCode}`);

    const options: DictOption[] = (res.data.data ?? []).map((item) => ({
      label: item.dictLabel,
      value: item.dictValue,
    }));
    dictCache.set(dictCode, options);
    return options;
  } catch (err) {
    console.error(`[PlannerSelect] 字典加载失败 (${dictCode}):`, err);
    return [];
  }
}

// ─────────────────────────────────────────────────────────────────────────────
/**
 * AssistantRenderer — 健康顾问 AI 工作台的 Standalone 渲染器。
 *
 * createRenderer(catalog, componentMap) 返回一个自包含的 React 组件，
 * 内部已处理好所有 Provider（State / Visibility / Action / Validation）。
 *
 * Props（使用时）：
 *   spec           : Spec 对象（来自 buildStructuredSpec）
 *   state          : 初始 state（对应 Spec 中的 state 字段）
 *   onAction       : 自定义动作回调（统一处理 saveToServer 等自定义 action）
 *   onStateChange  : 可选，监听 state 变化（用于将 state 同步至外部）
 *   loading        : 可选，Spec 流式加载中时传 true，组件可据此显示骨架屏
 *
 * componentMap 中每个组件接收 ComponentRenderProps<P>，包含：
 *   element  : UIElement，其 element.props 即 Spec 中声明的 props（已 Zod 校验）
 *   children : 已递归渲染的子节点 ReactNode
 *   emit     : (eventName) => void，触发 on.[eventName] 声明的动作
 *   on       : (eventName) => EventHandle，获取事件元数据（shouldPreventDefault 等）
 *   bindings : Record<propName, statePath>，$bindState 双向绑定的路径映射
 */
export const AssistantRenderer = createRenderer(assistantCatalog, {
  /**
   * PlannerCard — 卡片容器组件
   *
   * Standalone Mode 中 props 通过 element.props 访问（不再是顶层的 props 参数）。
   * children 由框架递归渲染后注入，对应 Spec 中 children 数组里的所有子元素。
   */
  PlannerCard: ({ element, children }) => {
    const { title, subtitle } = element.props;
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow-xs">
        <h4 className="text-sm font-bold text-slate-800">{title}</h4>
        {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
        {/* children 由框架注入，对应 Spec 中 children 数组里的所有子元素 */}
        <div className="mt-3 space-y-2">{children}</div>
      </div>
    );
  },

  /**
   * PlannerMetric — 只读指标展示
   */
  PlannerMetric: ({ element }) => {
    const { label, value } = element.props;
    return (
      <div className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
        <span className="text-xs text-slate-500">{label}</span>
        <span className="text-xs font-bold text-slate-700">{value}</span>
      </div>
    );
  },

  /**
   * PlannerInput — 双向绑定输入框
   *
   * Standalone Mode 下 useBoundProp 用法不变：
   *   useBoundProp(element.props.value, bindings?.value)
   *   框架通过 bindings.value 解析 $bindState 对应的 state 路径，
   *   读写操作由框架内部的 StateStore 完成（无需手动连接 StateProvider）。
   */
  PlannerInput: ({ element, bindings }) => {
    const { label, placeholder } = element.props;
    const [boundValue, setBoundValue] = useBoundProp<string | Record<string, unknown> | null>(
      element.props.value,
      bindings?.value,
    );
    const value = typeof boundValue === 'string' ? boundValue : '';

    return (
      <label className="block rounded-xl border border-slate-200 bg-white px-3 py-2">
        <span className="block text-[11px] font-semibold text-slate-500">{label}</span>
        <input
          value={value}
          onChange={(e) => setBoundValue(e.target.value)} // 用户输入 → 同步回 Spec state
          placeholder={placeholder ?? ''}
          className="mt-1 w-full border-0 bg-transparent text-xs text-slate-700 focus:outline-none"
        />
      </label>
    );
  },

  /**
   * PlannerButton — 动作触发按钮
   *
   * emit('press') 触发 Spec 中 on.press 声明的动作：
   *   - 若 action 是内置的（如 'setState'），框架直接执行
   *   - 若 action 是自定义的（如 'saveToServer'），框架回调 AssistantRenderer 的 onAction prop
   *
   * Standalone Mode 的关键：组件只负责 emit，业务逻辑完全在 onAction 中处理，
   * 组件本身对"点击后发生什么"完全无感。
   */
  PlannerButton: ({ element, emit }) => (
    <button
      type="button"
      onClick={() => emit('press')} // 发射 'press'，框架路由到 on.press 声明的 action
      className="w-full rounded-xl bg-brand px-3 py-2 text-xs font-bold text-white transition-colors hover:bg-brand-dark"
    >
      {element.props.label}
    </button>
  ),

  /**
   * PlannerNotice — 状态提示条
   *
   * visible 条件渲染由框架在组件外层处理，组件本身无需关心是否应该显示。
   * Standalone Mode 下 visible 逻辑同样由 createRenderer 内部自动处理。
   */
  PlannerNotice: ({ element }) => {
    const { text, tone } = element.props;
    const isSuccess = tone === 'success';
    return (
      <div
        className={`rounded-xl px-3 py-2 text-xs font-medium ${isSuccess
            ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
            : 'bg-brand/10 text-brand border border-brand/15'
          }`}
      >
        {text}
      </div>
    );
  },

  /**
   * PlannerSelect — 字典下拉选择框
   *
   * 工作流程：
   *   1. 组件挂载时用 element.props.dictCode 调 fetchDictOptions() 拉取选项
   *   2. 选项加载中/失败时显示对应状态文字
   *   3. 选中值通过 useBoundProp + bindings.value 双向绑定到 Spec state
   *
   * Standalone Mode 下 useBoundProp 写回操作由框架内部 StateStore 处理，
   * 无需手动连接 StateContext。
   */
  PlannerSelect: ({ element, bindings }) => {
    const { label, dictCode, placeholder } = element.props;

    // ── 选项列表状态 ────────────────────────────────────────────────────────
    const [options, setOptions] = useState<DictOption[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    useEffect(() => {
      if (!dictCode) return;
      setLoading(true);
      setError(false);
      fetchDictOptions(String(dictCode))
        .then((opts) => { setOptions(opts); setLoading(false); })
        .catch(() => { setError(true); setLoading(false); });
    }, [dictCode]);

    // ── 选中值双向绑定 ──────────────────────────────────────────────────────
    const [boundValue, setBoundValue] = useBoundProp<string | Record<string, unknown> | null>(
      element.props.value,
      bindings?.value,
    );
    const selectedValue = typeof boundValue === 'string' ? boundValue : '';

    return (
      <label className="block rounded-xl border border-slate-200 bg-white px-3 py-2">
        <span className="block text-[11px] font-semibold text-slate-500">{label}</span>
        <select
          value={selectedValue}
          onChange={(e) => setBoundValue(e.target.value)}
          disabled={loading || error}
          className="mt-1 w-full border-0 bg-transparent text-xs text-slate-700 focus:outline-none disabled:opacity-50"
        >
          <option value="" disabled>
            {loading ? '加载中…' : error ? '选项加载失败' : (placeholder ?? '请选择')}
          </option>
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>
    );
  },

  /**
   * PlannerTable — 服务端分页表格
   * 
   * 工作流程：
   * 1. 挂载时根据传入的 api 发送请求，附带 pageNum 参数
   * 2. 当用户点击分页（antd pagination onChange），由于绑定的 page 值改变
   * 3. 触发再次按照新页码拉取，更新结果。
   */
  PlannerTable: ({ element, bindings, emit }) => {
    const { title, api, columns, dataSource, rowActions } = element.props;

    const [data, setData] = useState<any[]>(dataSource || []);
    const [total, setTotal] = useState(dataSource?.length || 0);
    const [loading, setLoading] = useState(false);

    // currentPage 的双向绑定
    const [boundPage, setBoundPage] = useBoundProp<number | Record<string, unknown> | null>(
      element.props.currentPage,
      bindings?.currentPage,
    );
    // 默认页码是 1
    const page = typeof boundPage === 'number' ? boundPage : 1;

    useEffect(() => {
      let active = true;
      // 支持后端直接下发 dataSource 进行静态展示
      if (!api) {
        if (dataSource) {
          setData(dataSource);
          setTotal(dataSource.length);
        }
        return;
      }

      setLoading(true);
      apiClient.get(api, {
        // 请求后台时一般需要 pageNum 和 pageSize 字段
        params: { pageNum: page, pageSize: 5 }
      })
        .then(res => {
          if (!active) return;
          // 适配大多标准后端响应：包裹层可能是 res.data.data.records，也可能是 res.data.rows
          const records = res.data?.data?.rows || res.data?.data?.records || res.data?.rows || res.data?.data || [];
          const totalCount = res.data?.data?.total || res.data?.total || records.length || 0;
          setData(records);
          setTotal(totalCount);
          setLoading(false);
        })
        .catch(err => {
          console.error('表格数据获取失败:', err);
          setLoading(false);
        });

      return () => { active = false; };
    }, [api, page]);

    const tableColumns = useMemo(() => {
      const cols = Array.isArray(columns) ? [...columns] : [];
      if (rowActions && Array.isArray(rowActions) && rowActions.length > 0) {
        cols.push({
          title: '操作',
          key: 'action',
          render: (_: any, record: any) => (
            <div className="flex gap-3">
              {rowActions.map((action: any, idx: number) => (
                <button
                  key={idx}
                  type="button"
                  className="text-brand hover:text-brand-dark hover:underline text-[11px] font-bold transition-colors"
                  onClick={() => {
                    if (emit) {
                      emit(action.type || 'remoteQuery', { record, action });
                    }
                  }}
                >
                  {action.label}
                </button>
              ))}
            </div>
          )
        });
      }
      return cols;
    }, [columns, rowActions]);

    return (
      <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        {title && <h5 className="mb-3 text-[13px] font-bold text-slate-700">{title}</h5>}

        {/* 使用 Ant Design 的原生 Table 来做展示和分页控制 */}
        <Table
          size="small"
          dataSource={data}
          columns={tableColumns}
          loading={loading}
          // 根据实际后端的 id 或其它字段提供一个唯一 key
          rowKey={(record: any) => record.id || record.uid || JSON.stringify(record)}
          pagination={{
            current: page,
            pageSize: 5,
            total: total,
            onChange: (newPage) => setBoundPage(newPage),
            showSizeChanger: false, // 卡片区域小，建议禁用页面大小调节
          }}
          scroll={{ x: 'max-content' }} // 数据列太多时允许左右拖滚
          className="text-xs"
        />
      </div>
    );
  },

  PlannerDetailCard: ({ element }) => {
    const { title, items } = element.props;

    return (
      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-4 flex items-center justify-between border-b border-slate-100 pb-3">
          <h5 className="text-[14px] font-extrabold text-slate-800">
            {title || '详细资料'}
          </h5>
        </div>

        <Descriptions
          column={{ xxl: 3, xl: 3, lg: 2, md: 2, sm: 1, xs: 1 }}
          size="small"
          labelStyle={{ fontWeight: 600, color: 'red', whiteSpace: 'nowrap' }}
          contentStyle={{ color: '#0F172A', wordBreak: 'break-all' }}
        >
          {items?.map((item: any, idx: number) => {
            // 对长文本的 value 可以加省略或者弹窗，这里暂时直接渲染
            const displayValue = item.value === '-' || !item.value ? '暂无' : item.value;
            // 判断是否是类似 JSON 的过长字符串
            const isLongJson = displayValue.length > 50 && (displayValue.startsWith('{') || displayValue.startsWith('['));

            return (
              <Descriptions.Item key={idx} label={item.label} span={isLongJson ? 3 : 1}>
                {isLongJson ? (
                  <div className="max-h-24 overflow-y-auto w-full custom-scrollbar text-[11px] bg-slate-50 p-2 rounded border border-slate-100" title={displayValue}>
                    {displayValue}
                  </div>
                ) : (
                  <span className="text-[12px]">{displayValue}</span>
                )}
              </Descriptions.Item>
            );
          })}
        </Descriptions>
      </div>
    );
  },
});