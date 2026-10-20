export const API_BASE = (import.meta.env.VITE_API_BASE || '/api/v1').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  detail: unknown
  code?: string

  constructor(message: string, status: number, detail: unknown, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.code = code
  }
}

export function humanizeError(detail: unknown, fallback = '请求失败'): string {
  if (!detail) return fallback
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as Record<string, unknown>).msg)
        }
        return JSON.stringify(item)
      })
      .join('；')
  }
  if (typeof detail === 'object') {
    const record = detail as Record<string, unknown>
    if (typeof record.message === 'string') return record.message
    if (typeof record.detail === 'string') return record.detail
    return JSON.stringify(detail)
  }
  return fallback
}

async function parseError(response: Response): Promise<ApiError> {
  let payload: any = null
  try {
    payload = await response.json()
  } catch {
    // ignore non-JSON errors
  }
  const detail = payload?.detail ?? payload
  const message = humanizeError(detail, `请求失败 (${response.status})`)
  const code = typeof detail === 'object' && detail ? String(detail.code ?? '') : undefined
  return new ApiError(message, response.status, detail, code || undefined)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers || {}),
    },
    ...init,
  })
  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  get<T>(path: string): Promise<T> {
    return request<T>(path)
  },
  post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
  },
  patch<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
  },
  put<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, { method: 'PUT', body: JSON.stringify(body) })
  },
  delete<T>(path: string): Promise<T> {
    return request<T>(path, { method: 'DELETE' })
  },
}

export interface SSEMessage<T = any> {
  event: string
  data: T
}

/**
 * POST + read an SSE response (EventSource cannot POST).
 * Frames are separated by a blank line; `data:` lines are concatenated.
 */
export async function streamPost(
  path: string,
  body: unknown,
  onMessage: (message: SSEMessage) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) throw await parseError(response)
  if (!response.body) throw new ApiError('浏览器不支持流式响应', 500, null)

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  const dispatch = (frame: string) => {
    let event = 'message'
    const dataLines: string[] = []
    for (const rawLine of frame.split('\n')) {
      const line = rawLine.replace(/\r$/, '')
      if (!line || line.startsWith(':')) continue
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
    }
    if (!dataLines.length) return
    const raw = dataLines.join('\n')
    try {
      onMessage({ event, data: JSON.parse(raw) })
    } catch {
      onMessage({ event, data: raw })
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      dispatch(frame)
      boundary = buffer.indexOf('\n\n')
    }
  }
  buffer += decoder.decode()
  if (buffer.trim()) dispatch(buffer)
}
