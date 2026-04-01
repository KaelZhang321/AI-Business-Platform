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
