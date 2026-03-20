import { z } from 'zod'

const actionTypes = ['view_detail', 'refresh', 'export', 'open_link', 'trigger_task'] as const

export type UIActionType = (typeof actionTypes)[number]

const actionSchema = z.object({
  type: z.enum(actionTypes),
  label: z.string().optional(),
  url: z.string().optional(),
  params: z.record(z.string(), z.unknown()).optional(),
})

const tagSchema = z.object({
  label: z.string(),
  color: z.string().optional(),
})

const listItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string().optional(),
  status: z.string().optional(),
  tags: z.array(tagSchema).optional(),
  assignee: z.string().optional(),
  dueDate: z.string().optional(),
  meta: z.record(z.string(), z.unknown()).optional(),
})

const formFieldSchema = z.object({
  name: z.string(),
  label: z.string(),
  type: z.enum(['text', 'number', 'date', 'select']),
  required: z.boolean().default(false),
  placeholder: z.string().optional(),
  options: z
    .array(
      z.object({
        label: z.string(),
        value: z.string(),
      }),
    )
    .optional(),
})

const cardPropsSchema = z.object({
  title: z.string().optional(),
  subtitle: z.string().optional(),
  actions: z.array(actionSchema).optional(),
})

const tablePropsSchema = z.object({
  title: z.string().optional(),
  columns: z.array(z.string()),
  data: z.array(z.array(z.unknown())),
  actions: z.array(actionSchema).optional(),
})

const metricPropsSchema = z.object({
  label: z.string(),
  value: z.union([z.string(), z.number()]),
  change: z.number().optional(),
  format: z.enum(['currency', 'percent', 'number']).optional(),
  trend: z.enum(['up', 'down', 'flat']).optional(),
})

const listPropsSchema = z.object({
  title: z.string().optional(),
  items: z.array(listItemSchema),
  emptyText: z.string().optional(),
})

const formPropsSchema = z.object({
  fields: z.array(formFieldSchema),
  submitLabel: z.string().optional(),
})

const tagPropsSchema = tagSchema

const chartPropsSchema = z.object({
  title: z.string().optional(),
  kind: z.enum(['bar', 'line', 'pie', 'scatter', 'radar']),
  option: z.record(z.string(), z.unknown()),
})

type UISpecType = 'Card' | 'Table' | 'Metric' | 'List' | 'Form' | 'Tag' | 'Chart'

type ComponentSchema = Record<UISpecType, z.ZodTypeAny>

const componentProps: ComponentSchema = {
  Card: cardPropsSchema,
  Table: tablePropsSchema,
  Metric: metricPropsSchema,
  List: listPropsSchema,
  Form: formPropsSchema,
  Tag: tagPropsSchema,
  Chart: chartPropsSchema,
}

const createComponentSpec = <T extends UISpecType>(type: T, propsSchema: z.ZodTypeAny) =>
  z.object({
    type: z.literal(type),
    props: propsSchema.default({}),
    children: z
      .array(
        z.lazy(() => uiSpecSchema),
      )
      .optional(),
  })

const uiSpecSchemaBuilder = () =>
  z.union([
    createComponentSpec('Card', componentProps.Card),
    createComponentSpec('Table', componentProps.Table),
    createComponentSpec('Metric', componentProps.Metric),
    createComponentSpec('List', componentProps.List),
    createComponentSpec('Form', componentProps.Form),
    createComponentSpec('Tag', componentProps.Tag),
    createComponentSpec('Chart', componentProps.Chart),
  ])

const uiSpecSchema = z.lazy(uiSpecSchemaBuilder)

export type UISpec = z.infer<typeof uiSpecSchema>
export type UIAction = z.infer<typeof actionSchema>
export type ListItem = z.infer<typeof listItemSchema>

export function validateUISpec(spec: unknown) {
  const result = uiSpecSchema.safeParse(spec)
  if (result.success) {
    return { success: true, spec: result.data as UISpec }
  }
  const errors = result.error.errors.map((issue) => `${issue.path.join('.') || 'spec'}: ${issue.message}`)
  return { success: false, errors }
}
