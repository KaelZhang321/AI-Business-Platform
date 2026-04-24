/**
 * catalog.ts — 组件目录（类型声明 + 校验规则）
 */
import { defineCatalog } from '@json-render/core';
import { schema as jsonRenderSchema } from '@json-render/react/schema';
import { z } from 'zod';

const bindableValueSchema = z.union([
  z.string(),
  z.number(),
  z.boolean(),
  z.record(z.string(), z.unknown()),
]).nullable();

const infoItemSchema = z.object({
  label: z.string(),
  value: z.union([z.string(), z.number(), z.boolean(), z.null()]).optional().nullable(),
});

const toneSchema = z.enum(['neutral', 'blue', 'emerald', 'amber', 'rose', 'purple', 'cyan', 'indigo', 'slate']);

export const assistantCatalog = defineCatalog(jsonRenderSchema, {
  components: {
    PlannerCard: {
      props: z.object({
        title: z.string(),
        subtitle: z.string().nullable().optional(),
        headerRightText: z.string().nullable().optional(),
      }),
      description: '规划内容容器',
    },

    PlannerBlankContainer: {
      props: z.object({
        minHeight: z.number().nullable().optional(),
      }),
      description: '空白容器（仅边框样式，用于承载其他组件）',
    },

    PlannerMetric: {
      props: z.object({
        label: z.string(),
        value: z.string(),
      }),
      description: '规划指标条目',
    },

    PlannerMetricTiles: {
      props: z.object({
        tiles: z.array(
          z.object({
            label: z.string(),
            value: z.string(),
            desc: z.string().nullable().optional(),
            icon: z.string().nullable().optional(),
            tone: toneSchema.optional(),
          }),
        ),
        minColumnWidth: z.number().nullable().optional(),
      }),
      description: '指标卡片组（用于资产概览等多指标展示）',
    },

    PlannerInfoGrid: {
      props: z.object({
        items: z.array(infoItemSchema),
        minColumnWidth: z.number().nullable().optional(),
      }),
      description: '信息网格（label/value）',
    },

    PlannerSectionBlocks: {
      props: z.object({
        sections: z.array(
          z.object({
            title: z.string(),
            icon: z.string().nullable().optional(),
            tone: toneSchema.optional(),
            items: z.array(infoItemSchema),
          }),
        ),
        minColumnWidth: z.number().nullable().optional(),
      }),
      description: '分区块容器（用于生活方式、心理情绪等分组展示）',
    },

    PlannerHighlightNote: {
      props: z.object({
        text: z.string(),
        tone: z.enum(['info', 'success', 'warning', 'neutral']).nullable().optional(),
      }),
      description: '高亮说明块（备注/提示）',
    },

    PlannerOwnerMeta: {
      props: z.object({
        name: z.string(),
        executionDate: z.string().nullable().optional(),
        lastUpdateDate: z.string().nullable().optional(),
        executionLabel: z.string().nullable().optional(),
        updateLabel: z.string().nullable().optional(),
      }),
      description: '负责人及执行日期信息块',
    },

    PlannerInput: {
      props: z.object({
        label: z.string(),
        value: bindableValueSchema,
        placeholder: z.string().nullable().optional(),
        required: z.boolean().nullable().optional(),
      }),
      description: '可双向绑定的输入框',
    },

    PlannerForm: {
      props: z.object({
        formCode: z.string(),
        api: z.string().nullable().optional(),
        queryParams: z.record(z.string(), z.unknown()).optional(),
        body: z.record(z.string(), z.unknown()).optional(),
        flowNum: z.string().nullable().optional(),
        createdBy: z.string().nullable().optional(),
      }),
      description: '查询表单容器',
    },

    PlannerButton: {
      props: z.object({
        label: z.string(),
      }),
      description: '触发动作按钮',
    },

    PlannerNotice: {
      props: z.object({
        text: z.string(),
        tone: z.enum(['info', 'success', 'warning']).nullable().optional(),
      }),
      description: '状态提示',
    },

    PlannerSelect: {
      props: z.object({
        label: z.string(),
        dictCode: z.string(),
        value: bindableValueSchema,
        placeholder: z.string().nullable().optional(),
      }),
      description: '字典下拉选择框，选项从接口动态加载',
    },

    PlannerTable: {
      props: z.object({
        title: z.string().nullable().optional(),
        api: z.string().optional(),
        columns: z.array(z.record(z.string(), z.unknown())).optional(),
        dataSource: z.array(z.any()).optional(),
        rows: z.array(z.any()).optional(),
        rowActions: z.array(z.record(z.string(), z.unknown())).optional(),
        currentPage: z.union([z.number(), z.record(z.string(), z.unknown())]).nullable().optional(),
        total: z.number().nullable().optional(),
        pageSize: z.number().nullable().optional(),
        pageParam: z.string().nullable().optional(),
        pageSizeParam: z.string().nullable().optional(),
        queryParams: z.record(z.string(), z.unknown()).optional(),
        body: z.record(z.string(), z.unknown()).optional(),
        flowNum: z.string().nullable().optional(),
        createdBy: z.string().nullable().optional(),
      }),
      description: '动态数据表格，支持静态数据与服务端分页',
    },

    PlannerPagination: {
      props: z.object({
        enabled: z.boolean().nullable().optional(),
        total: z.number().nullable().optional(),
        currentPage: z.union([z.number(), z.record(z.string(), z.unknown())]).nullable().optional(),
        pageSize: z.number().nullable().optional(),
        pageParam: z.string().nullable().optional(),
        pageSizeParam: z.string().nullable().optional(),
        api: z.string().nullable().optional(),
        queryParams: z.record(z.string(), z.unknown()).optional(),
        body: z.record(z.string(), z.unknown()).optional(),
        flowNum: z.string().nullable().optional(),
        createdBy: z.string().nullable().optional(),
      }),
      description: '分页状态条（主要用于和 PlannerTable 联动展示）',
    },

    PlannerDetailCard: {
      props: z.object({
        title: z.string().nullable().optional(),
        items: z.array(
          z.object({
            label: z.string(),
            value: z.string().nullable().optional(),
          }),
        ),
      }),
      description: '详情属性卡片，用于展示 Key-Value 列表型数据',
    },
  },

  actions: {},
});
