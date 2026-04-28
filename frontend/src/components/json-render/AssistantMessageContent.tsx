/**
 * AssistantMessageContent.tsx — AI 消息内容渲染入口（Standalone Mode）
 *
 * 这是整个 JSON-Render 体系的最终消费层，负责将 AI 回复渲染为：
 *   1. 普通文本段落（逐行 <p>）
 *   2. 结构化交互卡片（当 Spec 存在时，在文本下方渲染 AssistantRenderer）
 *
 * Standalone Mode 的关键简化：
 *   不再需要手动嵌套 StateProvider / ActionProvider / VisibilityProvider / ValidationProvider，
 *   改为直接使用 <AssistantRenderer> 组件，所有 Provider 由 createRenderer 内部自动处理。
 *
 * 文件在整个体系中的位置：
 *   spec.ts          → 构建 DataPart 数组（文本 + Spec）
 *   catalog.ts       → 声明可用组件及其 Props 类型
 *   registry.tsx     → createRenderer 返回 AssistantRenderer（Standalone 自包含组件）
 *   AssistantMessageContent.tsx（本文件） → 消费 AssistantRenderer，处理 onAction 回调
 */
import { useJsonRenderMessage } from '@json-render/react';
import { useMemo } from 'react';
import { apiClient } from '../../services/api';
import { AssistantRenderer } from './registry';
import { buildJsonRenderParts } from './spec';

interface AssistantMessageContentProps {
  content: string; // AI 原始回复文本
}

export function AssistantMessageContent({ content }: AssistantMessageContentProps) {
  /**
   * buildJsonRenderParts(content) 构建 DataPart 数组：
   *   [{ type: 'text', text: '...' }, { type: SPEC_DATA_PART_TYPE, data: { spec: ... } }]
   */
  const parts = useMemo(() => buildJsonRenderParts(content), [content]);

  /**
   * useJsonRenderMessage(parts) 解析 DataPart 数组，返回：
   *   - text    : 纯文本内容
   *   - spec    : Spec 对象（可能为 null）
   *   - hasSpec : 是否存在有效的 Spec
   */
  const { text, spec, hasSpec } = useJsonRenderMessage(parts);

  /**
   * 从 Spec 中提取初始 state 传给 AssistantRenderer。
   * Standalone Mode 下 state prop 就是 createRenderer 内部 StateProvider 的 initialState。
   */
  const initialState = spec?.state && typeof spec.state === 'object'
    ? (spec.state as Record<string, unknown>)
    : {};

  /**
   * handleAction — 统一处理所有自定义动作（Standalone Mode 的核心）。
   *
   * Standalone Mode 下，所有 Spec 中 on.press.action 定义的自定义动作（非内置的
   * 'setState'/'navigate' 等）都会回调此函数，由业务层集中处理：
   *
   *   actionName : Spec 中 action 字段的值（如 'saveToServer'）
   *   params     : Spec 中 params 字段的值（框架已将 $bindState 解析为实际值）
   *
   * 相比 Provider Mode 的 handlers 机制，这里更简单直观——
   * 就是一个普通的 async 函数，switch 判断 actionName 即可。
   */
  const handleAction = async (
    actionName: string,
    params?: Record<string, unknown>,
  ) => {
    console.log(123213)
    switch (actionName) {
      /**
       * saveToServer — 将规划目标写入服务端。
       *
       * params.goal 已由框架将 { $bindState: '/plan/nextGoal' } 解析为 state 中的真实字符串值。
       * params.statePath 用于指示接口成功后需要更新的 state 路径（框架通过 return value 处理）。
       *
       * ⚠️ Standalone Mode 下 onAction 不能直接更新 state（没有 setState 参数）。
       * 若需要在 action 成功后更新 state，有两种方式：
       *   1. 在 Spec 中配置多个动作（先 saveToServer，再 setState）— 待框架支持
       *   2. 通过 onStateChange 在外部管理 state（受控模式）
       *   3. 最简单：让按钮的 visible 绑定接口调用结果（通过 Zustand/状态管理）
       */
      case 'saveToServer': {
        const goal = typeof params?.goal === 'string' ? params.goal : '';
        const apiPath = typeof params?.api === 'string' ? params.api : '';
        const body = typeof params?.body === 'object' ? params.body : {};
        console.log('Action params API:', params);
        try {
          let res;
          if (apiPath) {
            res = await apiClient.post(apiPath, { ...params });
          } else {
            res = await apiClient.post('/api/v1/consultant/plan/save', { goal });
          }

          // 通知 PlannerTable 数据更新（如果页面有 PlannerTable）
          if (res) {
            window.dispatchEvent(new CustomEvent('planner:table-data-update', {
              detail: { resData: res.data }
            }));
          }

          console.info('[AssistantMessageContent] 交互保存/查询完成', { apiPath, goal });
        } catch (err) {
          console.error('[AssistantMessageContent] saveToServer 失败:', err);
        }
        break;
      }

      default:
        console.warn(`[AssistantMessageContent] 未处理的 action: ${actionName}`, params);
    }
  };

  return (
    <>
      {/* 文本区域：按换行符拆分，每行渲染为独立的 <p> 标签 */}
      {/* {text.split('\n').map((line, index) => (
        <p key={`assistant-line-${index}`} className={index > 0 ? 'mt-2' : ''}>
          {line}
        </p>
      ))} */}

      {/**
       * 卡片区域：Standalone Mode 下直接使用 <AssistantRenderer>，
       * 无需任何 Provider 包装，所有内部状态管理由 createRenderer 自动处理。
       *
       * Props 说明：
       *   spec          : Spec 对象，框架据此递归渲染组件树
       *   state         : 初始 state（对应 Spec.state），框架内部持有
       *   onAction      : 自定义动作回调，框架路由所有非内置 action 到此函数
       *   loading       : 可选，流式加载中时传 true（Spec 流传输时可渐进渲染）
       */}
      {hasSpec && spec && (
        <div className="mt-3">
          <AssistantRenderer
            spec={spec}
            state={initialState}
            onAction={handleAction}
          />
        </div>
      )}
    </>
  );
}
