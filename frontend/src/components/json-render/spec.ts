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

const COMPLEX_SHOWCASE_KEYWORDS = /组件管理|展示组件|资产概览|身份与联系|健康状况|教育铺垫|负责人及执行日期/;
const MULTI_CARD_KEYWORDS = /多卡片|多卡|卡片布局|multi\s*-?\s*card/i;

export function buildMultiCardSpec(): Spec {
  return {
    root: 'multi-card-root',
    state: {},
    elements: {
      'multi-card-root': {
        type: 'PlannerBlankContainer',
        props: {
          "minHeight": 160
        },
        children: ['profile-card', 'risk-card', 'followup-card'],
      },

      'profile-card': {
        type: 'PlannerCard',
        props: {
          title: '基础信息卡',
          subtitle: '客户主档与联系信息',
          headerRightText: '基础',
        },
        children: ['profile-grid'],
      },
      'profile-grid': {
        type: 'PlannerInfoGrid',
        props: {
          minColumnWidth: 180,
          items: [
            { label: '客户姓名', value: '张三' },
            { label: '性别', value: '女' },
            { label: '年龄', value: '52' },
            { label: '联系电话', value: '13800138000' },
            { label: '最近体检日期', value: '2026-04-10' },
            { label: '主诉', value: '睡眠质量下降' },
          ],
        },
      },

      'risk-card': {
        type: 'PlannerCard',
        props: {
          title: '风险评估卡',
          subtitle: '关键健康指标概览',
          headerRightText: '风险',
        },
        children: ['risk-metrics', 'risk-note'],
      },
      'risk-metrics': {
        type: 'PlannerMetricTiles',
        props: {
          minColumnWidth: 170,
          tiles: [
            { label: '睡眠风险', value: '中', desc: '近30天波动较大', icon: 'moon', tone: 'amber' },
            { label: '情绪压力', value: '中高', desc: '需要持续干预', icon: 'heart', tone: 'rose' },
            { label: '代谢风险', value: '低', desc: '保持稳定', icon: 'activity', tone: 'emerald' },
          ],
        },
      },
      'risk-note': {
        type: 'PlannerHighlightNote',
        props: {
          text: '建议优先从作息管理与压力干预切入，2周后复评。',
          tone: 'warning',
        },
      },

      'followup-card': {
        type: 'PlannerCard',
        props: {
          title: '跟进计划卡',
          subtitle: '任务拆解与执行信息',
          headerRightText: '执行',
        },
        children: ['followup-table', 'followup-owner'],
      },
      'followup-table': {
        type: 'PlannerTable',
        props: {
          title: '本周跟进任务',
          columns: [
            { key: 'task', title: '任务', dataIndex: 'task' },
            { key: 'owner', title: '负责人', dataIndex: 'owner' },
            { key: 'dueDate', title: '截止日期', dataIndex: 'dueDate' },
            { key: 'status', title: '状态', dataIndex: 'status' },
          ],
          rows: [
            { id: 't1', task: '睡眠问卷回访', owner: '李健管', dueDate: '2026-04-18', status: '进行中' },
            { id: 't2', task: '饮食计划确认', owner: '王顾问', dueDate: '2026-04-19', status: '待开始' },
            { id: 't3', task: '复评时间预约', owner: '客服A', dueDate: '2026-04-20', status: '已完成' },
          ],
          total: 3,
          currentPage: 1,
          pageSize: 10,
        },
      },
      'followup-owner': {
        type: 'PlannerOwnerMeta',
        props: {
          name: '李健管',
          executionDate: '2026-04-15',
          lastUpdateDate: '2026-04-15',
        },
      },
    },
  };
}

export function buildComponentShowcaseSpec(): Spec {
  return {
    root: 'showcase-card',
    state: {},
    elements: {
      'showcase-card': {
        type: 'PlannerCard',
        props: {
          title: '客户画像结构化展示',
          subtitle: '通用原子 + 少量复合组件示例',
          headerRightText: 'AI草案',
        },
        children: [
          'asset-metric-tiles',
          'identity-info-grid',
          'lifestyle-section-blocks',
          'education-table',
          'remarks-note',
          'owner-meta',
        ],
      },
      'asset-metric-tiles': {
        type: 'PlannerMetricTiles',
        props: {
          minColumnWidth: 180,
          tiles: [
            {
              label: '医疗项目金总余额',
              value: '2,053,540',
              desc: '包含可用及冻结金额',
              icon: 'wallet',
              tone: 'blue',
            },
            {
              label: '可用余额',
              value: '2,043,360',
              desc: '当前可直接消费金额',
              icon: 'unlock',
              tone: 'emerald',
            },
            {
              label: '待收回余额',
              value: '446,880',
              desc: '预计近期可回收',
              icon: 'clock',
              tone: 'amber',
            },
            {
              label: '剩余项目数',
              value: '16',
              desc: '当前可用项目总数',
              icon: 'package',
              tone: 'cyan',
            },
          ],
        },
      },
      'identity-info-grid': {
        type: 'PlannerInfoGrid',
        props: {
          minColumnWidth: 180,
          items: [
            { label: '客户姓名', value: '张三' },
            { label: '性别', value: '女' },
            { label: '年龄', value: '52' },
            { label: '联系电话', value: '13800138000' },
            { label: '微信', value: 'zhangsan_wx' },
            { label: '婚姻状况', value: '已婚已育' },
          ],
        },
      },
      'lifestyle-section-blocks': {
        type: 'PlannerSectionBlocks',
        props: {
          minColumnWidth: 280,
          sections: [
            {
              title: '生活方式与习惯',
              icon: 'activity',
              tone: 'blue',
              items: [
                { label: '运动频率', value: '每周 3 次' },
                { label: '运动类型', value: '慢跑、瑜伽' },
                { label: '作息规律', value: '规律' },
                { label: '睡眠时长', value: '7 小时' },
              ],
            },
            {
              title: '心理与情绪',
              icon: 'heart',
              tone: 'rose',
              items: [
                { label: '常见情绪', value: '焦虑、疲惫' },
                { label: '情绪影响程度', value: '中度影响' },
                { label: '压力应对方式', value: '听音乐、运动' },
                { label: '支持需求', value: '倾听、专业建议' },
              ],
            },
          ],
        },
      },
      'education-table': {
        type: 'PlannerTable',
        props: {
          title: '教育铺垫记录',
          columns: [
            { key: 'round', title: '次数', dataIndex: 'round' },
            { key: 'time', title: '时间', dataIndex: 'time' },
            { key: 'content', title: '铺垫内容', dataIndex: 'content' },
            { key: 'feedback', title: '结果反馈', dataIndex: 'feedback' },
          ],
          rows: [
            {
              id: '1',
              round: '第1次',
              time: '2026-03-01',
              content: '睡眠管理重要性',
              feedback: '认可，愿意尝试',
            },
            {
              id: '2',
              round: '第2次',
              time: '2026-03-15',
              content: '功能医学检测介绍',
              feedback: '有兴趣，考虑中',
            },
          ],
          total: 2,
          currentPage: 1,
          pageSize: 10,
        },
      },
      'remarks-note': {
        type: 'PlannerHighlightNote',
        props: {
          text: '近期准备出国旅行，建议提前安排复查与随访。',
          tone: 'info',
        },
      },
      'owner-meta': {
        type: 'PlannerOwnerMeta',
        props: {
          name: '李健管',
          executionDate: '2026-04-15',
          lastUpdateDate: '2026-04-12',
        },
      },
    },
  };
}

export function buildStructuredSpec(message: string): Spec {
  // if (MULTI_CARD_KEYWORDS.test(message)) {
  return buildMultiCardSpec();
  // }

  if (COMPLEX_SHOWCASE_KEYWORDS.test(message)) {
    return buildComponentShowcaseSpec();
  }

  return buildComponentShowcaseSpec();

  // 根据 AI 回复内容判断卡片类型，动态设置标题和副标题
  const isPlanningMessage = /规划|建议|追踪|结果|治疗/.test(message);
  const title = isPlanningMessage ? '1+X 结构化健康规划' : '客户信息结构化视图';
  const subtitle = isPlanningMessage ? '支持状态绑定、动作触发与条件渲染' : '当前回复已同步为可操作卡片';

  // return {
  //   // root：Spec 的渲染入口，值为 elements 中某个元素的 ID
  //   root: 'planner-card',

  //   /**
  //    * state：卡片内部的全局状态仓库，类似 React 的 useState，但用 JSON 路径访问。
  //    * 路径格式遵循 RFC 6901 JSON Pointer：
  //    *   /plan          → state.plan
  //    *   /plan/confirmed → state.plan.confirmed
  //    */
  //   state: {
  //     plan: {
  //       nextGoal: '每周 3 次中低强度有氧',
  //       confirmed: false,   // 标记用户是否已点击"写入建议"按钮
  //       exerciseType: '',   // 运动类型选择结果（绑定 PlannerSelect）
  //     },
  //   },


  //   /**
  //    * elements：所有 UI 元素的定义表，key 是元素 ID，value 是元素描述。
  //    * - type：对应 registry.tsx 中注册的组件名称
  //    * - props：传递给组件的静态属性
  //    * - children：子元素 ID 数组，框架会按顺序渲染
  //    * - on：事件监听，key 是事件名（如 press），value 是要执行的动作
  //    * - visible：条件渲染规则，控制该元素是否显示
  //    */
  //   elements: {
  //     // 根容器：PlannerCard 组件，包裹所有子元素
  //     'planner-card': {
  //       type: 'PlannerCard',
  //       props: {
  //         title,
  //         subtitle,
  //       },
  //       // 按顺序渲染以下子元素，注意这里新增了 'customer-table'
  //       children: ['metric-1', 'metric-2', 'customer-table', 'exercise-select', 'goal-input', 'apply-btn', 'pending-notice', 'success-notice'],
  //     },

  //     // 指标展示：只读的 label + value 条目
  //     'metric-1': {
  //       type: 'PlannerMetric',
  //       props: {
  //         label: '改善指数',
  //         value: '15%',
  //       },
  //     },
  //     'metric-2': {
  //       type: 'PlannerMetric',
  //       props: {
  //         label: '下次复查',
  //         value: '2026-04-15',
  //       },
  //     },

  //     /**
  //      * 分页表格展示（我们刚刚新加进工程的组件）
  //      * 只需要写接口和列信息即可，翻页操作和请求会在 PlannerTable 内部自己完成
  //      */
  //     'customer-table': {
  //       type: 'PlannerTable',
  //       props: {
  //         title: '近期检查列表 (演示用地址)',
  //         // 这里填你们后端真实的带分页的业务接口
  //         api: '/api/v1/customers/records', 
  //         columns: [
  //           { dataIndex: 'examDate', title: '体检日期' },
  //           { dataIndex: 'hospital', title: '就诊机构' },
  //           { dataIndex: 'result', title: '异常项' },
  //         ],
  //         // 将目前表格停留在第几页，存入到 state 的某个变量里（如果不需要与外层交互可以不写）
  //         currentPage: { $bindState: '/plan/tableCurrentPage' } 
  //       }
  //     },

  //     /**
  //      * 字典下拉选择框：选项列表由组件内部根据 dictCode 调接口获取，Spec 只需声明字典编码。
  //      *
  //      * dictCode: 'exercise_type' → 组件会请求 GET /api/v1/system/dict/data/type/exercise_type
  //      * value: { $bindState: '/plan/exerciseType' } → 选中值双向绑定到 state.plan.exerciseType
  //      *
  //      * 优点：
  //      *   - Spec（AI 侧）不需要知道选项内容，只需要知道字典编码
  //      *   - 选项列表由前端组件动态加载，后端字典变更后自动生效
  //      *   - 带缓存：同一 dictCode 在整个会话中只请求一次
  //      */
  //     'exercise-select': {
  //       type: 'PlannerSelect',
  //       props: {
  //         label: '运动类型',
  //         dictCode: 'exercise_type',                      // 字典编码，对应后端字典表的 dict_type 字段
  //         value: { $bindState: '/plan/exerciseType' },    // 选中值绑定到 state.plan.exerciseType
  //         placeholder: '请选择运动类型',
  //       },
  //     },

  //     /**
  //      * 可编辑输入框：value 使用 $bindState 双向绑定到 state 中的路径。
  //      * { $bindState: '/plan/nextGoal' } 表示：
  //      *   - 读取时：从 state.plan.nextGoal 取值显示在输入框
  //      *   - 写入时：用户修改后自动同步回 state.plan.nextGoal
  //      * 这样无需手写 onChange 处理函数。
  //      */
  //     'goal-input': {
  //       type: 'PlannerInput',
  //       props: {
  //         label: '下月核心目标',
  //         value: { $bindState: '/plan/nextGoal' },
  //         placeholder: '例如：每晚 11 点前入睡',
  //       },
  //     },

  //     /**
  //      * 操作按钮：点击后触发 on.press 中定义的动作。
  //      * action: 'setState' 是框架内置动作，含义是"修改 state 中某个路径的值"。
  //      * params 字段：
  //      *   - statePath: '/plan/confirmed'
  //      *       → 指向 state.plan.confirmed（JSON Pointer 格式，/ 是层级分隔符）
  //      *   - value: true
  //      *       → 将 state.plan.confirmed 设置为 true
  //      * 效果：按钮点击 → confirmed 变 true → pending-notice 消失，success-notice 出现
  //      */
  //     'apply-btn': {
  //       type: 'PlannerButton',
  //       props: {
  //         label: '一键写入客户跟踪建议',
  //       },
  //       on: {
  //         press: {
  //           action: 'saveToServer',
  //           params: {
  //             statePath: '/plan/confirmed', // JSON Pointer：指向 state.plan.confirmed
  //             goal: { $bindState: '/plan/nextGoal' }
  //           },
  //         },
  //       },
  //     },

  //     /**
  //      * 条件渲染 - 方式一（取反）：
  //      * visible.$state: '/plan/confirmed' → 读取 state.plan.confirmed
  //      * visible.not: true                 → 对该值取反
  //      * 合并效果：confirmed === false 时显示（即按钮点击前显示引导文案）
  //      */
  //     'pending-notice': {
  //       type: 'PlannerNotice',
  //       props: {
  //         text: '可先编辑目标，再点击按钮写入建议。',
  //         tone: 'info',
  //       },
  //       visible: {
  //         $state: '/plan/confirmed',
  //         not: true, // confirmed 为 false 时显示，为 true 后隐藏
  //       },
  //     },

  //     /**
  //      * 条件渲染 - 方式二（直接绑定）：
  //      * visible.$state: '/plan/confirmed' → 直接读取该值
  //      * confirmed === true 时显示（即按钮点击后显示成功反馈）
  //      */
  //     'success-notice': {
  //       type: 'PlannerNotice',
  //       props: {
  //         text: '已写入客户建议并标记为本轮追踪重点。',
  //         tone: 'success',
  //       },
  //       visible: { $state: '/plan/confirmed' }, // confirmed 为 true 时显示
  //     },
  //   },
  // };
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
  let specObj = null;
  let textContent = message;

  // 1. 尝试将收到的内容当作大模型返回的真实 JSON 解析
  try {
    // 真实业务中，一旦接口能直接把 JSON 字符串下发，这里就能拦截并在内存恢复成对象
    const parsed = JSON.parse(message);
    if (parsed && typeof parsed === 'object' && parsed.spec) {
      specObj = parsed.spec;
      textContent = parsed.text || "已根据指令生成结构化卡片方案，请在旁侧查阅。";
    }
  } catch (e) {
    // 解析失败没关系，说明这是一条普通的纯文本回复（或者是还没接入 JSON 的兜底逻辑）
  }

  return [
    {
      // 文本部分：AI 的讲解会话，逐行渲染为 <p> 标签
      type: 'text',
      text: textContent,
    },
    {
      // Spec 部分：声明式 UI 规格
      type: SPEC_DATA_PART_TYPE,
      data: {
        type: 'flat', // flat 表示所有 elements 平铺在同一层
        spec: specObj || buildStructuredSpec(message), // 优先使用接口直出的 Spec JSON，如果没有，再回退到本地的关键词模糊匹配生成
      },
    },
  ];
}
