/**
 * catalog.ts — 组件目录（类型声明 + 校验规则）
 *
 * Catalog 是 @json-render 体系的"菜单"：
 * 它声明了哪些组件可以在 Spec 中使用，以及每个组件的 props 结构和类型约束。
 *
 * 作用：
 *   1. 让 Spec 中的 props 在运行时经过 Zod 校验，防止格式错误的数据传入组件
 *   2. 作为 registry.tsx 的类型参数，使组件实现享有完整的 TypeScript 类型推断
 *
 * 关系链：
 *   catalog.ts（声明/约束）
 *     → registry.tsx（具体 React 组件实现）
 *     → AssistantMessageContent.tsx（渲染入口）
 */
import { defineCatalog } from '@json-render/core';
import { schema as jsonRenderSchema } from '@json-render/react/schema';
import { z } from 'zod';

/**
 * assistantCatalog — 健康顾问 AI 工作台的组件目录。
 *
 * defineCatalog(baseSchema, extension) 将本地组件定义合并到框架基础 schema 中，
 * 返回一个可传给 defineRegistry 的类型安全目录。
 */
export const assistantCatalog = defineCatalog(jsonRenderSchema, {
  components: {
    /**
     * PlannerCard — 规划卡片容器
     * 用于包裹整个结构化回复区块，展示标题和副标题，内部通过 children 插槽渲染子元素。
     */
    PlannerCard: {
      props: z.object({
        title: z.string(),
        subtitle: z.string().nullable(), // 副标题可选，传 null 则不显示
      }),
      description: '规划内容容器',
    },

    /**
     * PlannerMetric — 只读指标条目
     * 用于展示单个数值型信息（如"改善指数 15%"），不可交互。
     */
    PlannerMetric: {
      props: z.object({
        label: z.string(), // 指标名称，显示在左侧
        value: z.string(), // 指标值，显示在右侧（加粗）
      }),
      description: '规划指标条目',
    },

    /**
     * PlannerInput — 可编辑输入框
     * 支持通过 $bindState 将 value 双向绑定到 Spec state，
     * value 类型是 union：既可以是普通字符串，也可以是 { $bindState: '/path' } 绑定对象。
     */
    PlannerInput: {
      props: z.object({
        label: z.string(),
        value: z.union([z.string(), z.record(z.string(), z.unknown())]).nullable(),
        placeholder: z.string().nullable(),
      }),
      description: '可双向绑定的输入框',
    },

    /**
     * PlannerButton — 动作触发按钮
     * 点击后触发 on.press 中声明的动作（如 setState）。
     * 无需在此处定义 onClick，框架通过 emit('press') 驱动。
     */
    PlannerButton: {
      props: z.object({
        label: z.string(), // 按钮文案
      }),
      description: '触发动作按钮',
    },

    /**
     * PlannerNotice — 状态提示条
     * 常与 visible 条件渲染配合使用，根据 state 变化动态显示/隐藏。
     * tone 控制样式：'info' 蓝色引导，'success' 绿色反馈。
     */
    PlannerNotice: {
      props: z.object({
        text: z.string(),
        tone: z.enum(['info', 'success']).nullable(),
      }),
      description: '状态提示',
    },

    /**
     * PlannerSelect — 字典下拉选择框
     *
     * 选项列表不写在 Spec 里，而是由组件实现（registry.tsx）根据 dictCode 调接口获取。
     * 这样 AI 只需声明"用哪个字典"，不需要知道选项内容，选项由前端动态加载。
     *
     * Props：
     *   label    : 下拉框标签（显示在上方的说明文字）
     *   dictCode : 字典编码，对应后端字典接口的查询参数（如 'exercise_type'）
     *   value    : 当前选中值，支持 $bindState 双向绑定到 state
     *   placeholder : 未选中时的提示文字（可选）
     *
     * Spec 示例：
     *   type: 'PlannerSelect'
     *   props:
     *     label: '运动类型'
     *     dictCode: 'exercise_type'        ← 字典编码，组件据此调接口
     *     value: { $bindState: '/plan/exerciseType' }  ← 选中值双向绑定
     *     placeholder: '请选择运动类型'
     */
    PlannerSelect: {
      props: z.object({
        label: z.string(),
        dictCode: z.string(), // 字典编码，组件用它来调字典接口
        value: z.union([z.string(), z.record(z.string(), z.unknown())]).nullable(),
        placeholder: z.string().nullable(),
      }),
      description: '字典下拉选择框，选项从接口动态加载',
    },
  },

  /**
   * actions：Standalone Mode 下此字段留空（动作由外部 onAction 回调统一处理）。
   * defineCatalog 类型要求该字段存在，故保留空对象。
   * 如切换回 Provider Mode（defineRegistry），在此处添加 action 声明即可。
   */
  actions: {},
});


/**
 * ⚠️ Standalone Mode 说明：
 *
 * 使用 createRenderer（Standalone Mode）时，catalog 中无需声明 actions。
 * 所有自定义动作（如 saveToServer）通过 <AssistantRenderer onAction={...}> 的回调统一处理。
 *
 * 如切换回 Provider Mode（defineRegistry），可在此处重新添加 actions 声明。
 */
