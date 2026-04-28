export function formatDateTime(value?: string | null) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN', {
    hour12: false,
  })
}

export function prettyJson(value: unknown) {
  if (value == null) {
    return '{}'
  }

  if (typeof value === 'string') {
    try {
      return JSON.stringify(JSON.parse(value), null, 2)
    } catch {
      return value
    }
  }

  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

export function parseJsonInput(input?: string) {
  if (!input || !input.trim()) {
    return undefined
  }

  return JSON.parse(input)
}

function safeParseJson(value: unknown) {
  if (value == null) {
    return undefined
  }

  if (typeof value === 'string') {
    if (!value.trim()) {
      return undefined
    }
    try {
      return JSON.parse(value)
    } catch {
      return undefined
    }
  }

  if (typeof value === 'object') {
    return value
  }

  return undefined
}

export interface FieldOrchestrationPaginationConfig {
  requestTarget?: 'query' | 'body'
  currentKey?: string
  sizeKey?: string
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function humanizeFieldLabel(key: string) {
  const lastSegment = key.split('.').at(-1)?.replace(/\[\]/g, '') ?? key
  return lastSegment
    .replace(/[_-]+/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^\w/, (char) => char.toUpperCase())
}

function toStandardKey(rawKey: string) {
  const lastSegment = rawKey.split('.').at(-1)?.replace(/\[\]/g, '') ?? rawKey
  const parts = lastSegment
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map((part) => part.toLowerCase())

  if (!parts.length) {
    return rawKey
  }

  return parts
    .map((part, index) => (index === 0 ? part : `${part.charAt(0).toUpperCase()}${part.slice(1)}`))
    .join('')
}

function inferFieldType(schemaNode: any, sampleValue: unknown) {
  const type = typeof schemaNode?.type === 'string' ? schemaNode.type : undefined
  const format = typeof schemaNode?.format === 'string' ? schemaNode.format : undefined

  if (Array.isArray(schemaNode?.enum) && schemaNode.enum.length) {
    return 'select'
  }
  if (format === 'date' || format === 'date-time') {
    return 'date'
  }
  if (type === 'integer' || type === 'number' || typeof sampleValue === 'number') {
    return 'number'
  }
  if (type === 'boolean' || typeof sampleValue === 'boolean') {
    return 'select'
  }
  return 'text'
}

function isCompositeNode(schemaNode: any, sampleValue: unknown) {
  if (schemaNode?.type === 'object' || isPlainObject(schemaNode?.properties)) {
    return true
  }
  if (schemaNode?.type === 'array' || schemaNode?.items) {
    return true
  }
  if (Array.isArray(sampleValue)) {
    return true
  }
  return isPlainObject(sampleValue)
}

function getSchemaProperties(schemaNode: any) {
  return isPlainObject(schemaNode?.properties) ? (schemaNode.properties as Record<string, unknown>) : {}
}

function collectExistingFieldMap(config: any) {
  const fieldMap = new Map<string, { rawKey: string; standardKey: string; label: string; type: string }>()
  const fieldConfig = isPlainObject(config?.fieldConfig) ? config.fieldConfig : {}
  const groups = Array.isArray(fieldConfig.groups) ? fieldConfig.groups : []
  const render = Array.isArray(fieldConfig.render) ? fieldConfig.render : []

  for (const group of groups) {
    if (!Array.isArray(group?.fields)) {
      continue
    }
    for (const field of group.fields) {
      if (field && typeof field.rawKey === 'string') {
        fieldMap.set(field.rawKey, field)
      }
    }
  }
  for (const field of render) {
    if (field && typeof field.rawKey === 'string') {
      fieldMap.set(field.rawKey, field)
    }
  }
  return fieldMap
}

function createField(rawKey: string, schemaNode: any, sampleValue: unknown, existingFieldMap: Map<string, { rawKey: string; standardKey: string; label: string; type: string }>) {
  const existing = existingFieldMap.get(rawKey)
  return {
    rawKey,
    standardKey: existing?.standardKey ?? toStandardKey(rawKey),
    label: existing?.label ?? humanizeFieldLabel(rawKey),
    type: existing?.type ?? inferFieldType(schemaNode, sampleValue),
  }
}

function walkCompositeFields(
  schemaNode: any,
  sampleValue: unknown,
  currentPath: string,
  existingFieldMap: Map<string, { rawKey: string; standardKey: string; label: string; type: string }>,
  collector: Array<{ rawKey: string; standardKey: string; label: string; type: string }>,
) {
  const schemaProperties = getSchemaProperties(schemaNode)
  const sampleObject = isPlainObject(sampleValue) ? sampleValue : {}
  const keys = Array.from(new Set([...Object.keys(schemaProperties), ...Object.keys(sampleObject)]))

  if (schemaNode?.type === 'array' || schemaNode?.items || Array.isArray(sampleValue)) {
    const itemSchema = schemaNode?.items
    const firstSample = Array.isArray(sampleValue) && sampleValue.length ? sampleValue[0] : undefined
    if (isCompositeNode(itemSchema, firstSample)) {
      walkCompositeFields(itemSchema, firstSample, `${currentPath}[]`, existingFieldMap, collector)
      return
    }
    collector.push(createField(`${currentPath}[]`, itemSchema, firstSample, existingFieldMap))
    return
  }

  for (const key of keys) {
    const childSchema = schemaProperties[key]
    const childSample = sampleObject[key]
    const rawKey = currentPath ? `${currentPath}.${key}` : key

    if (isCompositeNode(childSchema, childSample)) {
      walkCompositeFields(childSchema, childSample, rawKey, existingFieldMap, collector)
      continue
    }
    collector.push(createField(rawKey, childSchema, childSample, existingFieldMap))
  }
}

export function buildFieldOrchestration(responseSchemaInput?: unknown, sampleResponseInput?: unknown, currentConfigInput?: unknown) {
  const schemaRoot = safeParseJson(responseSchemaInput)
  const sampleRoot = safeParseJson(sampleResponseInput)
  const currentConfig = safeParseJson(currentConfigInput)
  const existingFieldMap = collectExistingFieldMap(currentConfig)

  const fieldConfig = isPlainObject((currentConfig as any)?.fieldConfig) ? (currentConfig as any).fieldConfig : {}
  const ignore = Array.isArray(fieldConfig.ignore) ? fieldConfig.ignore : []
  const passthrough = Array.isArray(fieldConfig.passthrough) ? fieldConfig.passthrough : []
  const pagination = isPlainObject(fieldConfig.pagination) ? fieldConfig.pagination : undefined

  const schemaProperties = getSchemaProperties(schemaRoot)
  const sampleProperties = isPlainObject(sampleRoot) ? sampleRoot : {}
  const topLevelKeys = Array.from(new Set([...Object.keys(schemaProperties), ...Object.keys(sampleProperties)]))

  const groups: Array<{
    groupKey: string
    label: string
    fields: Array<{ rawKey: string; standardKey: string; label: string; type: string }>
  }> = []
  const render: Array<{ rawKey: string; standardKey: string; label: string; type: string }> = []

  for (const key of topLevelKeys) {
    const schemaNode = schemaProperties[key]
    const sampleValue = sampleProperties[key]

    if (isCompositeNode(schemaNode, sampleValue)) {
      const groupFields: Array<{ rawKey: string; standardKey: string; label: string; type: string }> = []
      walkCompositeFields(schemaNode, sampleValue, key, existingFieldMap, groupFields)
      if (groupFields.length) {
        groups.push({
          groupKey: key.replace(/[^\w]+/g, '_'),
          label: humanizeFieldLabel(key),
          fields: groupFields,
        })
      }
      continue
    }

    render.push(createField(key, schemaNode, sampleValue, existingFieldMap))
  }

  return {
    fieldConfig: {
      ignore,
      passthrough,
      groups,
      render,
      ...(pagination ? { pagination } : {}),
    },
  }
}

export function parseFieldOrchestrationConfig(input?: unknown) {
  const parsed = safeParseJson(input)
  if (isPlainObject(parsed?.fieldConfig)) {
    return parsed as {
      fieldConfig: {
        ignore?: unknown[]
        passthrough?: unknown[]
        groups?: unknown[]
        render?: unknown[]
        pagination?: FieldOrchestrationPaginationConfig
      }
    }
  }
  return {
    fieldConfig: {
      ignore: [],
      passthrough: [],
      groups: [],
      render: [],
    },
  }
}

export function inferDefaultPaginationConfig(
  method?: string,
  operationSafety?: string,
): FieldOrchestrationPaginationConfig | undefined {
  if (operationSafety !== 'list') {
    return undefined
  }
  if (String(method ?? '').toUpperCase() === 'POST') {
    return {
      requestTarget: 'body',
      currentKey: 'pageNo',
      sizeKey: 'pageSize',
    }
  }
  return {
    requestTarget: 'query',
    currentKey: 'current',
    sizeKey: 'size',
  }
}

export function mergePaginationConfigIntoFieldOrchestration(
  fieldOrchestrationInput: unknown,
  paginationConfig?: FieldOrchestrationPaginationConfig,
) {
  const config = parseFieldOrchestrationConfig(fieldOrchestrationInput)
  const nextFieldConfig = {
    ...config.fieldConfig,
  } as Record<string, unknown>

  if (
    paginationConfig
    && paginationConfig.requestTarget
    && paginationConfig.currentKey
    && paginationConfig.sizeKey
  ) {
    nextFieldConfig.pagination = {
      requestTarget: paginationConfig.requestTarget,
      currentKey: paginationConfig.currentKey,
      sizeKey: paginationConfig.sizeKey,
    }
  } else {
    delete nextFieldConfig.pagination
  }

  return {
    ...config,
    fieldConfig: nextFieldConfig,
  }
}

export function summarizeSpec(spec?: Record<string, unknown>) {
  if (!spec) {
    return { root: '-', elementCount: 0 }
  }

  const root = typeof spec.root === 'string' ? spec.root : '-'
  const elements = spec.elements
  const elementCount =
    elements && typeof elements === 'object' && !Array.isArray(elements)
      ? Object.keys(elements as Record<string, unknown>).length
      : 0

  return { root, elementCount }
}
