import { defineStore } from 'pinia'
import type {
  AgentTraceNode,
  ChatHistoryRow,
  ChatSession,
  ChatUiMessage,
  Device,
  ParsedIntent,
  RetrievalPayload,
  RAGHit,
  SceneRunState,
  SceneRunStep,
  ToolTraceItem,
} from '@/types'
import { api, streamPost } from '@/services/http'
import { uid } from '@/utils/format'
import { useUiStore } from '@/stores/ui'
import { useHomeStore } from '@/stores/home'

const SESSION_KEY = 'smarthome.chat.session'
let currentAbort: AbortController | null = null
let initialized = false

function newSessionId(): string {
  return `s_${uid()}`
}

function createAssistantMessage(): ChatUiMessage {
  return {
    id: uid('m_'),
    role: 'assistant',
    content: '',
    createdAt: Date.now(),
    streaming: true,
    status: 'running',
    intent: null,
    trace: [],
    retrieval: null,
    tools: [],
    scene: null,
    error: null,
    executionId: null,
    options: [],
    notes: [],
  }
}

function asText(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessionId: localStorage.getItem(SESSION_KEY) || newSessionId(),
    sessions: [] as ChatSession[],
    messages: [] as ChatUiMessage[],
    streaming: false,
    loading: false,
    initialized: false,
    historyOpen: false,
    mode: 'offline' as 'llm' | 'offline',
    error: null as string | null,
    suggestions: [
      '打开客厅主灯',
      '空调调到 26 度',
      '开启观影模式',
      '现在室内温湿度怎么样',
      '空调多少度最省电',
    ],
  }),
  getters: {
    hasMessages(state): boolean {
      return state.messages.length > 0
    },
    lastAssistant(state): ChatUiMessage | null {
      for (let index = state.messages.length - 1; index >= 0; index -= 1) {
        if (state.messages[index].role === 'assistant') return state.messages[index]
      }
      return null
    },
    latestIntent(state): ParsedIntent | null {
      return this.lastAssistant?.intent || null
    },
    latestRetrieval(state): RetrievalPayload | null {
      return this.lastAssistant?.retrieval || null
    },
  },
  actions: {
    persistSession() {
      try {
        localStorage.setItem(SESSION_KEY, this.sessionId)
      } catch {
        // ignore
      }
    },
    async initialize() {
      if (initialized) return
      initialized = true
      this.persistSession()
      await Promise.all([this.loadSessions(), this.loadCurrentMessages()])
    },
    async loadSessions() {
      try {
        const response = await api.get<{ sessions: ChatSession[] }>('/chat/sessions?limit=30')
        this.sessions = response.sessions
      } catch {
        // ignore; history drawer can show empty
      }
    },
    async loadCurrentMessages() {
      if (!this.sessionId) return
      this.loading = true
      try {
        const response = await api.get<{ messages: ChatHistoryRow[] }>(
          `/chat/sessions/${this.sessionId}/messages?limit=100`,
        )
        this.messages = response.messages.map((row) => this.mapHistoryMessage(row))
        const lastAssistant = [...this.messages].reverse().find((message) => message.role === 'assistant')
        if (lastAssistant?.mode) this.mode = lastAssistant.mode
      } catch {
        this.messages = []
      } finally {
        this.loading = false
      }
    },
    mapHistoryMessage(row: ChatHistoryRow): ChatUiMessage {
      const meta = row.meta || {}
      if (row.role === 'user') {
        return {
          id: `h_${row.id}`,
          role: 'user',
          content: row.content,
          createdAt: new Date(row.created_at).getTime(),
          trace: [],
          tools: [],
        }
      }
      return {
        id: `h_${row.id}`,
        role: 'assistant',
        content: row.content,
        createdAt: new Date(row.created_at).getTime(),
        streaming: false,
        status: asText(meta.status) || 'success',
        trace: [],
        tools: [],
        intent: null,
        retrieval: null,
        executionId: asText(meta.execution_id) || null,
        mode: this.mode,
        options: [],
      }
    },
    async openSession(sessionId: string) {
      if (this.streaming) this.stop()
      this.sessionId = sessionId
      this.persistSession()
      this.historyOpen = false
      await this.loadCurrentMessages()
    },
    async newSession() {
      if (this.streaming) this.stop()
      this.sessionId = newSessionId()
      this.persistSession()
      this.messages = []
      this.error = null
      this.historyOpen = false
    },
    async deleteSession(sessionId: string) {
      const ui = useUiStore()
      const confirmed = await ui.askConfirm('删除这段对话记录？', '删除对话', true)
      if (!confirmed) return
      try {
        await api.delete(`/chat/sessions/${sessionId}`)
        await this.loadSessions()
        if (sessionId === this.sessionId) await this.newSession()
        ui.success('对话已删除')
      } catch (error) {
        ui.toastFromError(error, '删除对话失败')
      }
    },
    stop() {
      currentAbort?.abort()
      currentAbort = null
      this.streaming = false
      const assistant = this.messages[this.messages.length - 1]
      if (assistant?.role === 'assistant' && assistant.streaming) {
        assistant.streaming = false
        assistant.status = assistant.status === 'running' ? 'stopped' : assistant.status
        if (!assistant.content) assistant.content = '已停止本次回复。'
      }
    },
    async send(rawText: string, options: { voice?: boolean } = {}) {
      const ui = useUiStore()
      const home = useHomeStore()
      const text = rawText.trim()
      if (!text || this.streaming) return
      this.error = null
      this.messages.push({
        id: uid('m_'),
        role: 'user',
        content: text,
        createdAt: Date.now(),
        trace: [],
        tools: [],
      })
      this.messages.push(createAssistantMessage())
      // Read the message back through the reactive array so every mutation
      // below is tracked by Vue (mutating the raw object would not re-render).
      const assistant = this.messages[this.messages.length - 1]
      this.streaming = true
      this.persistSession()
      currentAbort = new AbortController()

      try {
        await streamPost(
          '/chat/stream',
          { message: text, session_id: this.sessionId, voice: Boolean(options.voice) },
          ({ event, data }) => {
            this.handleEvent(assistant, event, data)
          },
          currentAbort.signal,
        )
        if (assistant.streaming) {
          assistant.streaming = false
          if (assistant.status === 'running') assistant.status = 'success'
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          assistant.streaming = false
          assistant.status = 'stopped'
          if (!assistant.content) assistant.content = '已停止本次回复。'
          return
        }
        const message = error instanceof Error ? error.message : '连接智能助手失败'
        assistant.error = message
        assistant.streaming = false
        assistant.status = 'failed'
        if (!assistant.content) {
          assistant.content = `抱歉，连接智能助手时出现问题：${message}`
        }
        this.error = message
        ui.error(message)
      } finally {
        this.streaming = false
        currentAbort = null
        await this.loadSessions()
        home.refreshSnapshot()
      }
    },
    handleEvent(assistant: ChatUiMessage, event: string, data: any) {
      const ui = useUiStore()
      switch (event) {
        case 'run_start':
          if (data.session_id) {
            this.sessionId = data.session_id
            this.persistSession()
          }
          if (data.mode) this.mode = data.mode
          assistant.mode = data.mode
          assistant.status = 'running'
          break
        case 'node_start':
          assistant.trace.push({
            key: uid('n_'),
            node: String(data.node || ''),
            label: String(data.label || data.node || '处理中'),
            status: 'running',
            startedAt: Date.now(),
          })
          break
        case 'node_end': {
          const candidates = [...assistant.trace]
            .reverse()
            .filter((node) => node.node === data.node && node.status === 'running')
          const target = candidates[0]
          if (target) {
            target.status = 'done'
            target.duration_ms = Number(data.duration_ms) || 0
            target.summary = asText(data.summary) || target.summary
          }
          break
        }
        case 'retrieval':
          assistant.retrieval = {
            intents: (data.intents || []) as RAGHit[],
            knowledge: (data.knowledge || []) as RAGHit[],
            latency_ms: Number(data.latency_ms) || 0,
            backend: asText(data.backend) || 'local',
          }
          break
        case 'intent': {
          assistant.intent = data.intent as ParsedIntent
          assistant.options = data.intent?.options || []
          assistant.notes = (data.notes || []) as string[]
          break
        }
        case 'tool_call': {
          const tool: ToolTraceItem = {
            callId: asText(data.call_id) || uid('call_'),
            name: asText(data.name),
            args: data.args || {},
            label: asText(data.label) || asText(data.name),
            status: 'running',
          }
          assistant.tools.push(tool)
          break
        }
        case 'tool_result': {
          let tool = assistant.tools.find((item) => item.callId === data.call_id)
          if (!tool) {
            tool = {
              callId: asText(data.call_id) || uid('call_'),
              name: asText(data.name),
              args: data.args || {},
              label: asText(data.name),
              status: 'running',
            }
            assistant.tools.push(tool)
          }
          tool.status = data.ok ? 'ok' : 'error'
          tool.message = asText(data.message)
          tool.duration_ms = Number(data.duration_ms) || 0
          if (data.device) tool.device = data.device as Device
          break
        }
        case 'scene_start': {
          const total = Number(data.total_steps) || 0
          assistant.scene = {
            sceneId: asText(data.scene_id),
            name: asText(data.name) || '场景',
            icon: asText(data.icon) || 'sparkles',
            description: asText(data.description),
            status: 'running',
            condition: null,
            steps: Array.from({ length: total }, (_, index) => ({
              index: index + 1,
              total,
              label: `动作 ${index + 1}`,
              status: 'pending' as const,
            })),
            startedAt: Date.now(),
          }
          break
        }
        case 'scene_condition': {
          if (assistant.scene) {
            assistant.scene.condition = {
              passed: Boolean(data.passed),
              reason: asText(data.reason),
              optional: Boolean(data.optional),
            }
          }
          break
        }
        case 'scene_step': {
          if (!assistant.scene) break
          const index = Number(data.index) - 1
          const step: SceneRunStep = {
            index: Number(data.index),
            total: Number(data.total),
            label: asText(data.label),
            device_id: asText(data.device_id),
            device_name: asText(data.device_name),
            status: 'running',
          }
          if (index >= 0 && index < assistant.scene.steps.length) {
            assistant.scene.steps.splice(index, 1, step)
          } else {
            assistant.scene.steps.push(step)
          }
          break
        }
        case 'scene_step_result': {
          const step = assistant.scene?.steps.find((item) => item.index === Number(data.index))
          if (step) {
            step.status = data.ok ? 'done' : 'failed'
            step.message = asText(data.message)
          }
          break
        }
        case 'scene_step_skipped': {
          const step = assistant.scene?.steps.find((item) => item.index === Number(data.index))
          if (step) {
            step.status = 'skipped'
            step.message = asText(data.reason)
          }
          break
        }
        case 'scene_fallback':
          if (assistant.scene) {
            assistant.scene.fallback = {
              success: Boolean(data.success),
              results: data.results || [],
            }
          }
          break
        case 'scene_done':
          if (assistant.scene && data.result) {
            assistant.scene.status = data.result.status || assistant.scene.status
            assistant.scene.message = asText(data.result.message)
          }
          break
        case 'token':
          assistant.content += asText(data.content)
          break
        case 'response':
          assistant.content = asText(data.content) || assistant.content
          break
        case 'notice':
          if (data.message) {
            assistant.notes?.push(String(data.message))
          }
          break
        case 'error':
          assistant.error = asText(data.message) || '执行出现异常'
          if (!assistant.content) {
            // The backend will usually send a fallback response right after.
            assistant.content = ''
          }
          break
        case 'done': {
          assistant.streaming = false
          assistant.status = asText(data.status) || 'success'
          assistant.executionId = asText(data.execution_id) || null
          assistant.mode = data.mode || assistant.mode
          if (assistant.scene && data.status) {
            assistant.scene.status = data.status
            assistant.scene.finishedAt = Date.now()
          }
          if (data.status === 'failed' && assistant.error) {
            ui.warning('本次执行未能完成，请查看轨迹')
          }
          break
        }
        default:
          break
      }
    },
  },
})
