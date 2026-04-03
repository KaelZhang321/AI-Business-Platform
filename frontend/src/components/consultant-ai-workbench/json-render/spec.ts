/**
 * spec.ts — JSON-Render 规格构建器
 *
 * 这个文件负责把 AI 的文本回复转换成结构化的声明式 UI 描述对象（Spec）。
 * 框架读取 Spec 后，会自动渲染出对应的 React 组件树，无需手写 JSX。
 *
 * 整体数据流：
 *   AI 文本回复
 *     → buildStructuredSpec()  构建 JSON Spec
 *     → buildJsonRenderParts() 打包成 DataPart 数组
 *     → @json-render/react 解析并渲染为 React 组件
 */
import { SPEC_DATA_PART_TYPE } from '@json-render/core';
import type { DataPart, Spec } from '@json-render/react';

export function buildStructuredSpec(message: string): Spec {
  // 根据 AI 回复内容判断卡片类型，动态设置标题和副标题
  const isPlanningMessage = /规划|建议|追踪|结果|治疗/.test(message);
  const title = isPlanningMessage ? '1+X 结构化健康规划' : '客户信息结构化视图';
  const subtitle = isPlanningMessage ? '支持状态绑定、动作触发与条件渲染' : '当前回复已同步为可操作卡片';

  return {
    // root：Spec 的渲染入口，值为 elements 中某个元素的 ID
    root: 'planner-card',

    /**
     * state：卡片内部的全局状态仓库，类似 React 的 useState，但用 JSON 路径访问。
     * 路径格式遵循 RFC 6901 JSON Pointer：
     *   /plan          → state.plan
     *   /plan/confirmed → state.plan.confirmed
     */
    state: {
      plan: {
        nextGoal: '每周 3 次中低强度有氧',
        confirmed: false,   // 标记用户是否已点击"写入建议"按钮
        exerciseType: '',   // 运动类型选择结果（绑定 PlannerSelect）
      },
    },


    /**
     * elements：所有 UI 元素的定义表，key 是元素 ID，value 是元素描述。
     * - type：对应 registry.tsx 中注册的组件名称
     * - props：传递给组件的静态属性
     * - children：子元素 ID 数组，框架会按顺序渲染
     * - on：事件监听，key 是事件名（如 press），value 是要执行的动作
     * - visible：条件渲染规则，控制该元素是否显示
     */
    elements: {
      // 根容器：PlannerCard 组件，包裹所有子元素
      'planner-card': {
        type: 'PlannerCard',
        props: {
          title,
          subtitle,
        },
        // 按顺序渲染以下子元素
        children: ['metric-1', 'metric-2', 'exercise-select', 'goal-input', 'apply-btn', 'pending-notice', 'success-notice'],
      },

      // 指标展示：只读的 label + value 条目
      'metric-1': {
        type: 'PlannerMetric',
        props: {
          label: '改善指数',
          value: '15%',
        },
      },
      'metric-2': {
        type: 'PlannerMetric',
        props: {
          label: '下次复查',
          value: '2026-04-15',
        },
      },

      /**
       * 字典下拉选择框：选项列表由组件内部根据 dictCode 调接口获取，Spec 只需声明字典编码。
       *
       * dictCode: 'exercise_type' → 组件会请求 GET /api/v1/system/dict/data/type/exercise_type
       * value: { $bindState: '/plan/exerciseType' } → 选中值双向绑定到 state.plan.exerciseType
       *
       * 优点：
       *   - Spec（AI 侧）不需要知道选项内容，只需要知道字典编码
       *   - 选项列表由前端组件动态加载，后端字典变更后自动生效
       *   - 带缓存：同一 dictCode 在整个会话中只请求一次
       */
      'exercise-select': {
        type: 'PlannerSelect',
        props: {
          label: '运动类型',
          dictCode: 'exercise_type',                      // 字典编码，对应后端字典表的 dict_type 字段
          value: { $bindState: '/plan/exerciseType' },    // 选中值绑定到 state.plan.exerciseType
          placeholder: '请选择运动类型',
        },
      },

      /**
       * 可编辑输入框：value 使用 $bindState 双向绑定到 state 中的路径。
       * { $bindState: '/plan/nextGoal' } 表示：
       *   - 读取时：从 state.plan.nextGoal 取值显示在输入框
       *   - 写入时：用户修改后自动同步回 state.plan.nextGoal
       * 这样无需手写 onChange 处理函数。
       */
      'goal-input': {
        type: 'PlannerInput',
        props: {
          label: '下月核心目标',
          value: { $bindState: '/plan/nextGoal' },
          placeholder: '例如：每晚 11 点前入睡',
        },
      },

      /**
       * 操作按钮：点击后触发 on.press 中定义的动作。
       * action: 'setState' 是框架内置动作，含义是"修改 state 中某个路径的值"。
       * params 字段：
       *   - statePath: '/plan/confirmed'
       *       → 指向 state.plan.confirmed（JSON Pointer 格式，/ 是层级分隔符）
       *   - value: true
       *       → 将 state.plan.confirmed 设置为 true
       * 效果：按钮点击 → confirmed 变 true → pending-notice 消失，success-notice 出现
       */
      'apply-btn': {
        type: 'PlannerButton',
        props: {
          label: '一键写入客户跟踪建议',
        },
        on: {
          press: {
            action: 'saveToServer',
            params: {
              statePath: '/plan/confirmed', // JSON Pointer：指向 state.plan.confirmed
              goal: { $bindState: '/plan/nextGoal' }
            },
          },
        },
      },

      /**
       * 条件渲染 - 方式一（取反）：
       * visible.$state: '/plan/confirmed' → 读取 state.plan.confirmed
       * visible.not: true                 → 对该值取反
       * 合并效果：confirmed === false 时显示（即按钮点击前显示引导文案）
       */
      'pending-notice': {
        type: 'PlannerNotice',
        props: {
          text: '可先编辑目标，再点击按钮写入建议。',
          tone: 'info',
        },
        visible: {
          $state: '/plan/confirmed',
          not: true, // confirmed 为 false 时显示，为 true 后隐藏
        },
      },

      /**
       * 条件渲染 - 方式二（直接绑定）：
       * visible.$state: '/plan/confirmed' → 直接读取该值
       * confirmed === true 时显示（即按钮点击后显示成功反馈）
       */
      'success-notice': {
        type: 'PlannerNotice',
        props: {
          text: '已写入客户建议并标记为本轮追踪重点。',
          tone: 'success',
        },
        visible: { $state: '/plan/confirmed' }, // confirmed 为 true 时显示
      },
    },
  };
}

/**
 * buildJsonRenderParts — 将 AI 文本 + Spec 打包成 DataPart 数组。
 *
 * DataPart 是 @json-render 的消息单元格式，支持混合内容：
 *   - type: 'text'                  → 普通文本，渲染为段落
 *   - type: SPEC_DATA_PART_TYPE     → JSON Spec，框架解析后渲染为交互卡片
 *
 * 最终由 AssistantMessageContent 组件消费：
 *   useJsonRenderMessage(parts) → 分离出 text 和 spec，分别渲染
 */
export function buildJsonRenderParts(message: string): DataPart[] {
  return [
    {
      // 文本部分：AI 原始回复，逐行渲染为 <p> 标签
      type: 'text',
      text: message,
    },
    {
      // Spec 部分：声明式 UI 规格，由框架解析渲染为交互卡片组件
      type: SPEC_DATA_PART_TYPE,
      data: {
        type: 'flat', // flat 表示所有 elements 平铺在同一层，框架用 root 字段确定入口
        spec: buildStructuredSpec(message),
      },
    },
  ];
}

