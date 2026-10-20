export type DeviceType =
  | 'light'
  | 'ac'
  | 'curtain'
  | 'purifier'
  | 'humidifier'
  | 'socket'
  | 'speaker'
  | 'vacuum'
  | 'sensor'

export type CapabilityType = 'boolean' | 'range' | 'enum' | 'readonly'

export interface CapabilityOption {
  value: string
  label: string
}

export interface Capability {
  key: string
  label: string
  type: CapabilityType
  min?: number
  max?: number
  step?: number
  unit?: string
  options?: CapabilityOption[]
  default?: boolean | number | string
}

export interface Device {
  id: string
  name: string
  room: string
  room_id: string
  type: DeviceType
  type_label: string
  online: boolean
  icon: string
  sort_order: number
  properties: Record<string, any>
  capabilities: Capability[]
  updated_at: string
}

export interface Environment {
  indoor_temp: number
  humidity: number
  pm25: number
  co2: number
  lux: number
  outdoor_temp: number
  outdoor_weather: string
  power_w: number
  period: string
  updated_at: string
}

export interface RoomClimate {
  id: string
  temperature: number
  humidity: number
}

export interface RoomMeta {
  id: string
  name: string
  icon: string
}

export interface Snapshot {
  devices: Device[]
  environment: Environment
  rooms: RoomClimate[]
  room_meta: RoomMeta[]
  period: string
  timestamp: string
}

export interface SceneCondition {
  type: 'time' | 'temperature' | 'humidity' | 'device_property'
  op?: string
  value?: any
  room?: string
  device_id?: string
  property?: string
  optional?: boolean
  label?: string
}

export interface SceneStep {
  device_id: string
  params: Record<string, any>
  label?: string
  delay_ms?: number
  critical?: boolean
  when?: SceneCondition | null
}

export interface Scene {
  id: string
  name: string
  icon: string
  description: string
  condition: SceneCondition | null
  steps: SceneStep[]
  fallback: SceneStep[]
  builtin: boolean
  enabled: boolean
  created_at: string
  updated_at: string
  step_count?: number
  fallback_count?: number
}

export interface RAGHit {
  id: string
  score: number
  text: string
  kind: 'intent' | 'knowledge'
  intent: string
  category: string
  device_type: string
  answer: string
  metadata: Record<string, any>
}

export interface IntentAction {
  intent: string
  device_ids: string[]
  params: Record<string, any>
  label: string
}

export interface ClarifyOption {
  label: string
  device_id: string
}

export interface ParsedIntent {
  intent_type: 'control' | 'query' | 'scene' | 'chat' | 'knowledge' | 'clarify' | string
  intent: string
  confidence: number
  source: string
  actions: IntentAction[]
  targets: string[]
  slots: Record<string, any>
  scene_id?: string | null
  direct_reply?: string | null
  clarify?: string | null
  options: ClarifyOption[]
  pending?: Record<string, any> | null
  knowledge: RAGHit[]
  room?: string | null
}

export interface RetrievalPayload {
  intents: RAGHit[]
  knowledge: RAGHit[]
  latency_ms: number
  backend: string
}

export interface AgentTraceNode {
  key: string
  node: string
  label: string
  status: 'running' | 'done'
  duration_ms?: number
  summary?: string
  startedAt: number
}

export interface ToolTraceItem {
  callId: string
  name: string
  args: Record<string, any>
  label: string
  status: 'running' | 'ok' | 'error'
  message?: string
  duration_ms?: number
  device?: Device
}

export interface SceneRunStep {
  index: number
  total: number
  label: string
  device_id?: string
  device_name?: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped'
  message?: string
}

export interface SceneRunState {
  sceneId: string
  name: string
  icon: string
  description?: string
  status: 'idle' | 'running' | 'success' | 'partial' | 'failed' | 'skipped'
  condition?: {
    passed: boolean
    reason: string
    optional?: boolean
  } | null
  steps: SceneRunStep[]
  fallback?: {
    success: boolean
    results: Array<{ label: string; ok: boolean; message: string }>
  } | null
  message?: string
  error?: string
  startedAt: number
  finishedAt?: number
}

export interface ChatUiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: number
  streaming?: boolean
  status?: string
  intent?: ParsedIntent | null
  trace: AgentTraceNode[]
  retrieval?: RetrievalPayload | null
  tools: ToolTraceItem[]
  scene?: SceneRunState | null
  error?: string | null
  executionId?: string | null
  mode?: 'llm' | 'offline'
  options?: ClarifyOption[]
  notes?: string[]
}

export interface ChatSession {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface ChatHistoryRow {
  id: number
  session_id: string
  role: 'user' | 'assistant'
  content: string
  meta: Record<string, any>
  created_at: string
}

export interface Execution {
  id: string
  session_id: string
  kind: 'chat' | 'scene' | string
  title: string
  input: string
  intent: ParsedIntent | Record<string, any>
  tool_calls: Array<Record<string, any>>
  trace: Array<Record<string, any>>
  result: Record<string, any>
  status: string
  duration_ms: number
  created_at: string
}

export interface EmbeddingStatus {
  provider: string
  model: string
  dim: number
  fallback: string | null
}

export interface RAGStatus {
  backend: string
  collection: string
  count: number
  intents: number
  knowledge: number
  dim: number
  healthy: boolean
  embedding: EmbeddingStatus
  requested_backend: string
  degraded: boolean
  latency_ms: number
  error: string | null
}

export interface SystemStatus {
  app: {
    name: string
    version: string
    started_at: string
    uptime_seconds: number
    demo_mode: boolean
  }
  llm: {
    enabled: boolean
    model: string
    base_url: string
    provider: string
    last_error: string | null
  }
  rag: RAGStatus
  simulator: {
    running: boolean
    interval: number
    tick: number
  }
  events: { subscribers: number }
  counts: Record<string, number>
}

export interface ToolSchema {
  name: string
  description: string
  parameters: Record<string, any>
}

export interface GraphTopology {
  nodes: Array<{ id: string; label: string; kind: string; description: string }>
  edges: string[][]
  scene_nodes: Array<{ id: string; label: string }>
}

export interface HistoryPoint {
  t: number
  value: number
}

export interface ToastItem {
  id: number
  level: 'success' | 'error' | 'info' | 'warning'
  message: string
}
