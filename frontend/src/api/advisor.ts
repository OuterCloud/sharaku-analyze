// 投资顾问 API（SSE 流式对话）

export interface KnowledgeDocInfo {
  path: string
  title: string
  chars: number
}

export interface KnowledgeStats {
  doc_count: number
  total_chars: number
  docs: KnowledgeDocInfo[]
}

export interface AdvisorStatus {
  success: boolean
  configured: boolean
  model: string
  knowledge: KnowledgeStats
  error?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/** SSE 事件类型 */
export type AdvisorEvent =
  | { type: 'meta'; ticker: string; name: string; current_price: number | null; knowledge_docs: number; model: string }
  | { type: 'delta'; content: string }
  | { type: 'done' }
  | { type: 'error'; message: string }

export async function getAdvisorStatus(): Promise<AdvisorStatus> {
  const res = await fetch('/api/advisor/status')
  return res.json()
}

export interface AdvisorChatParams {
  ticker: string
  question: string
  costBasis?: number
  horizonDays?: number
  history?: ChatMessage[]
  /** 追问时复用缓存的市场上下文，false 强制重新采集 */
  useCachedContext?: boolean
  signal?: AbortSignal
}

/**
 * 发起流式对话。通过回调逐块返回内容。
 *
 * 使用 fetch + ReadableStream 而非 EventSource，因为需要 POST 传递较大的
 * 对话历史，且 EventSource 不支持自定义请求方法。
 */
export async function streamAdvisorChat(
  params: AdvisorChatParams,
  onEvent: (event: AdvisorEvent) => void,
): Promise<void> {
  const body = new FormData()
  body.append('ticker', params.ticker)
  body.append('question', params.question)
  body.append('cost_basis', String(params.costBasis ?? 0))
  body.append('horizon_days', String(params.horizonDays ?? 30))
  body.append('history', JSON.stringify(params.history ?? []))
  body.append('use_cached_context', params.useCachedContext === false ? '0' : '1')

  const res = await fetch('/api/advisor/chat', {
    method: 'POST',
    body,
    signal: params.signal,
  })

  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const err = await res.json()
      message = err.detail || err.message || message
    } catch {
      // 响应体非 JSON，沿用状态码
    }
    onEvent({ type: 'error', message })
    return
  }

  if (!res.body) {
    onEvent({ type: 'error', message: 'Response body is not readable' })
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // SSE 以空行分隔事件
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''

    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data:')) continue
      const payload = line.slice(5).trim()
      if (!payload) continue
      try {
        onEvent(JSON.parse(payload) as AdvisorEvent)
      } catch {
        // 忽略无法解析的分片
      }
    }
  }
}
