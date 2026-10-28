export const number = (value: unknown, digits = 1) =>
  Number.isFinite(Number(value))
    ? Number(value).toLocaleString(undefined, { maximumFractionDigits: digits })
    : '—'
export const percent = (value: unknown) => `${number(Number(value) * 100)}%`
export const label = (value: unknown) => String(value ?? 'Unavailable').replaceAll('_', ' ')
export const short = (value: string | null | undefined, length = 12) =>
  value ? `${value.slice(0, length)}…` : '—'

export function routeFromHash(hash: string) {
  const value = hash.replace(/^#\/?/, '') || 'overview'
  const aliases: Record<string, string> = { alerts: 'security', recovery: 'healing' }
  return aliases[value] || value
}

export function csvCell(value: unknown) {
  let text = String(value ?? '')
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`
  return `"${text.replaceAll('"', '""')}"`
}

export function toCSV(rows: Record<string, unknown>[]) {
  if (!rows.length) return ''
  const keys = [...new Set(rows.flatMap((row) => Object.keys(row)))]
  return [
    keys.map(csvCell).join(','),
    ...rows.map((row) =>
      keys
        .map((key) => csvCell(typeof row[key] === 'object' ? JSON.stringify(row[key]) : row[key]))
        .join(','),
    ),
  ].join('\r\n')
}

export function download(name: string, value: unknown, csv = false) {
  const blob = new Blob(
    [csv ? toCSV(Array.isArray(value) ? value : []) : JSON.stringify(value, null, 2)],
    { type: csv ? 'text/csv;charset=utf-8' : 'application/json' },
  )
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function matchedExperiments(
  records: {
    seed: number
    horizon: number
    episodes: number
    environment_config?: Record<string, unknown>
  }[],
) {
  return (
    records.length > 1 &&
    records.every(
      (record) =>
        record.seed === records[0].seed &&
        record.horizon === records[0].horizon &&
        record.episodes === records[0].episodes &&
        JSON.stringify(record.environment_config || {}) ===
          JSON.stringify(records[0].environment_config || {}),
    )
  )
}

export class ApiError extends Error {
  code: string
  requestId?: string | null
  constructor(message: string, code: string, requestId?: string | null) {
    super(message)
    this.code = code
    this.requestId = requestId
  }
}

export function assertSnapshot(value: unknown): Record<string, unknown> {
  const row = value as Record<string, unknown> | null
  const metrics = row?.metrics as Record<string, unknown> | undefined
  const arrays = ['nodes', 'alerts', 'recovery', 'history', 'recent_events', 'partitioned_links']
  if (
    !row ||
    typeof row !== 'object' ||
    typeof row.instance_id !== 'string' ||
    typeof row.mode !== 'string' ||
    typeof row.running !== 'boolean' ||
    (row.revision !== undefined &&
      (typeof row.revision !== 'number' || !Number.isFinite(row.revision) || row.revision < 0)) ||
    (row.instance_started_at_ns !== undefined &&
      (typeof row.instance_started_at_ns !== 'string' ||
        !/^\d{1,20}$/.test(row.instance_started_at_ns))) ||
    !row.config ||
    typeof row.config !== 'object' ||
    !row.consensus ||
    typeof row.consensus !== 'object' ||
    arrays.some((key) => !Array.isArray(row[key])) ||
    !metrics ||
    ['simulated_seconds', 'height', 'quorum', 'throughput'].some(
      (key) => typeof metrics[key] !== 'number' || !Number.isFinite(metrics[key]),
    ) ||
    !(row.nodes as Record<string, unknown>[]).every(
      (node) =>
        node &&
        typeof node.id === 'string' &&
        typeof node.trust_score === 'number' &&
        Number.isFinite(node.trust_score) &&
        node.telemetry &&
        typeof node.telemetry === 'object',
    )
  ) {
    throw new ApiError(
      'An invalid simulator snapshot was rejected; the last valid measurements are retained.',
      'invalid_snapshot',
    )
  }
  return row
}

export function newestSnapshot(
  current: Record<string, unknown> | null,
  next: Record<string, unknown>,
): Record<string, unknown> {
  if (!current) return next
  if (current.instance_id === next.instance_id) {
    return Number(current.revision || 0) > Number(next.revision || 0) ? current : next
  }
  return BigInt(String(current.instance_started_at_ns || '0')) >
    BigInt(String(next.instance_started_at_ns || '0'))
    ? current
    : next
}

export async function request<T = unknown>(
  path: string,
  {
    token,
    method = 'GET',
    body,
    signal,
  }: { token?: string; method?: string; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  let response
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      signal,
      headers: {
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
  } catch (error) {
    if (
      typeof error === 'object' &&
      error !== null &&
      'name' in error &&
      error.name === 'AbortError'
    )
      throw error
    throw new ApiError(
      'The API could not be reached. Check the local service and retry.',
      'network_unavailable',
    )
  }
  let data
  try {
    data = await response.json()
  } catch {
    throw new ApiError(
      'The API returned an unreadable response.',
      'invalid_response',
      response.headers.get('x-request-id'),
    )
  }
  if (!response.ok)
    throw new ApiError(
      data.error?.detail || 'Request failed',
      data.error?.code || 'request_failed',
      data.error?.request_id,
    )
  return data as T
}
