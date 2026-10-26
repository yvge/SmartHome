<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  Activity,
  CheckCircle2,
  ChevronRight,
  Clock,
  GitBranch,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  Timer,
  Wrench,
  XCircle,
} from 'lucide-vue-next'
import { api } from '@/services/http'
import { useUiStore } from '@/stores/ui'
import type { Execution } from '@/types'
import { formatDateTime, relativeTime, statusLabel } from '@/utils/format'

const route = useRoute()
const ui = useUiStore()

const executions = ref<Execution[]>([])
const loading = ref(true)
const detail = ref<Execution | null>(null)
const detailLoading = ref(false)
const kindFilter = ref<'all' | 'chat' | 'scene'>('all')
const statusFilter = ref<'all' | 'success' | 'partial' | 'failed'>('all')
const query = ref('')
let timer: number | undefined

const filtered = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return executions.value.filter((row) => {
    if (kindFilter.value !== 'all' && row.kind !== kindFilter.value) return false
    if (statusFilter.value !== 'all' && row.status !== statusFilter.value) return false
    if (
      needle
      && !`${row.title}${row.input}${row.id}`.toLowerCase().includes(needle)
    ) return false
    return true
  })
})

const summary = computed(() => {
  const total = executions.value.length
  const success = executions.value.filter((row) => row.status === 'success').length
  const failed = executions.value.filter((row) => row.status === 'failed').length
  const durations = executions.value.map((row) => row.duration_ms).filter(Boolean)
  const avg = durations.length
    ? Math.round(durations.reduce((sum, value) => sum + value, 0) / durations.length)
    : 0
  return { total, success, failed, avg }
})

const timeline = computed(() => {
  if (!detail.value) return []
  const events = detail.value.trace || []
  const nodes: Array<{
    key: string
    label: string
    status: 'running' | 'done'
    duration?: number
    summary?: string
  }> = []
  const pending = new Map<string, number>()
  for (const event of events) {
    if (event.type === 'node_start') {
      nodes.push({
        key: `${event.node}-${event.seq}`,
        label: event.label || event.node,
        status: 'running',
      })
      pending.set(event.node, nodes.length - 1)
    } else if (event.type === 'node_end') {
      const index = pending.get(event.node)
      if (index !== undefined && nodes[index]) {
        nodes[index].status = 'done'
        nodes[index].duration = Number(event.duration_ms) || 0
        nodes[index].summary = event.summary
        pending.delete(event.node)
      }
    }
  }
  return nodes
})

const toolCalls = computed(() => {
  if (!detail.value) return []
  const calls = new Map<string, any>()
  for (const event of detail.value.trace || []) {
    if (event.type === 'tool_call') {
      calls.set(event.call_id, {
        id: event.call_id,
        name: event.name,
        label: event.label,
        args: event.args,
        status: 'running',
        message: '',
        duration: 0,
      })
    } else if (event.type === 'tool_result') {
      const call = calls.get(event.call_id) || {
        id: event.call_id,
        name: event.name,
        label: event.name,
        args: event.args,
      }
      call.status = event.ok ? 'ok' : 'error'
      call.message = event.message
      call.duration = event.duration_ms || 0
      calls.set(event.call_id, call)
    }
  }
  if (!calls.size && Array.isArray(detail.value.tool_calls)) {
    for (const [index, call] of detail.value.tool_calls.entries()) {
      calls.set(`stored_${index}`, {
        id: `stored_${index}`,
        name: call.name,
        label: call.name,
        args: call.args,
        status: call.ok ? 'ok' : 'error',
        message: call.message,
        duration: 0,
      })
    }
  }
  return Array.from(calls.values())
})

const sceneEvents = computed(() => {
  if (!detail.value) return []
  return (detail.value.trace || []).filter((event) =>
    ['scene_start', 'scene_condition', 'scene_step_result', 'scene_fallback', 'scene_done', 'scene_step_skipped'].includes(event.type),
  )
})

const intentInfo = computed(() => {
  const intent = detail.value?.intent as Record<string, any> | undefined
  if (!intent || !intent.intent_type) return null
  return intent
})

const responseText = computed(() => {
  const result = detail.value?.result as Record<string, any> | undefined
  return (result?.response as string) || ''
})

const errorText = computed(() => {
  const result = detail.value?.result as Record<string, any> | undefined
  return (result?.error as string) || ''
})

const sceneResult = computed(() => {
  const result = detail.value?.result as Record<string, any> | undefined
  return result?.scene_result || null
})

const intentTypeLabel: Record<string, string> = {
  control: '设备控制',
  query: '状态查询',
  scene: '场景执行',
  chat: '闲聊',
  knowledge: '知识问答',
  clarify: '澄清确认',
}

function statusTone(status: string): string {
  if (status === 'success') return 'good'
  if (status === 'partial' || status === 'skipped' || status === 'fallback') return 'warn'
  if (status === 'failed') return 'bad'
  return 'neutral'
}

async function loadExecutions() {
  loading.value = true
  try {
    const response = await api.get<{ executions: Execution[] }>('/system/executions?limit=100')
    executions.value = response.executions
    const focus = typeof route.query.focus === 'string' ? route.query.focus : null
    if (focus) {
      const target = response.executions.find((row) => row.id === focus)
      if (target) await selectExecution(target, false)
    } else if (!detail.value && response.executions.length) {
      await selectExecution(response.executions[0], false)
    }
  } catch (error) {
    ui.toastFromError(error, '运行记录加载失败')
  } finally {
    loading.value = false
  }
}

async function selectExecution(row: Execution, fetchDetail = true) {
  if (fetchDetail) {
    detailLoading.value = true
    try {
      const response = await api.get<{ execution: Execution }>(`/system/executions/${row.id}`)
      detail.value = response.execution
    } catch (error) {
      ui.toastFromError(error, '运行详情加载失败')
      detail.value = row
    } finally {
      detailLoading.value = false
    }
  } else {
    detail.value = row
  }
}

function compactArgs(args: Record<string, any> | undefined): string {
  if (!args) return '—'
  return Object.entries(args)
    .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join(' · ')
}

function formatDuration(ms: number | undefined): string {
  if (!ms) return '—'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

watch(
  () => route.query.focus,
  (focus) => {
    if (typeof focus !== 'string') return
    const target = executions.value.find((row) => row.id === focus)
    if (target) selectExecution(target, false)
  },
)

onMounted(async () => {
  await loadExecutions()
  timer = window.setInterval(loadExecutions, 30000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <div class="page executions-page">
    <section class="page-head">
      <div>
        <div class="eyebrow">执行记录</div>
        <h1>运行轨迹</h1>
        <p class="lede">
          每次对话与场景执行都会被完整记录：从意图解析到设备动作，花了多久、结果如何，都能回看。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" :disabled="loading" @click="loadExecutions">
          <RefreshCw :size="14" :class="{ spin: loading }" />
          刷新
        </button>
      </div>
    </section>

    <section class="exec-stats">
      <div class="exec-stat">
        <span class="exec-stat-label">总运行</span>
        <strong>{{ summary.total }}</strong>
        <span class="exec-stat-note">最近 100 条</span>
      </div>
      <div class="exec-stat">
        <span class="exec-stat-label">成功</span>
        <strong class="good">{{ summary.success }}</strong>
        <span class="exec-stat-note">{{ summary.total ? Math.round((summary.success / summary.total) * 100) : 0 }}%</span>
      </div>
      <div class="exec-stat">
        <span class="exec-stat-label">失败</span>
        <strong class="bad">{{ summary.failed }}</strong>
        <span class="exec-stat-note">需排查</span>
      </div>
      <div class="exec-stat">
        <span class="exec-stat-label">平均耗时</span>
        <strong>{{ formatDuration(summary.avg) }}</strong>
        <span class="exec-stat-note">端到端</span>
      </div>
    </section>

    <div class="exec-layout">
      <section class="panel exec-list-panel">
        <div class="exec-filters">
          <div class="segmented">
            <button :class="{ active: kindFilter === 'all' }" @click="kindFilter = 'all'">全部</button>
            <button :class="{ active: kindFilter === 'chat' }" @click="kindFilter = 'chat'">对话</button>
            <button :class="{ active: kindFilter === 'scene' }" @click="kindFilter = 'scene'">场景</button>
          </div>
          <select v-model="statusFilter" class="select status-select" aria-label="按状态筛选">
            <option value="all">全部状态</option>
            <option value="success">成功</option>
            <option value="partial">部分完成</option>
            <option value="failed">失败</option>
          </select>
        </div>
        <div class="exec-search">
          <Search :size="12" />
          <input v-model="query" placeholder="搜索输入或执行 ID" aria-label="搜索运行记录" />
        </div>

        <div class="exec-list">
          <button
            v-for="row in filtered"
            :key="row.id"
            class="exec-row"
            :class="{ active: detail?.id === row.id }"
            @click="selectExecution(row)"
          >
            <span class="exec-status-dot" :class="statusTone(row.status)"></span>
            <div class="exec-row-main">
              <div class="exec-row-top">
                <span class="exec-row-title">{{ row.title || row.input || 'Agent 执行' }}</span>
                <span class="exec-row-time">{{ relativeTime(row.created_at) }}</span>
              </div>
              <div class="exec-row-meta">
                <span class="exec-kind" :class="row.kind">{{ row.kind === 'scene' ? '场景' : '对话' }}</span>
                <span>{{ statusLabel(row.status) }}</span>
                <span>·</span>
                <span>{{ formatDuration(row.duration_ms) }}</span>
                <span class="exec-row-id mono">{{ row.id.slice(-8) }}</span>
              </div>
            </div>
            <ChevronRight :size="12" class="exec-chevron" />
          </button>

          <div v-if="loading && !executions.length" class="exec-loading">
            <Loader2 :size="16" class="spin" /> 正在加载运行记录…
          </div>
          <div v-else-if="!filtered.length" class="empty-state">
            <Activity :size="20" />
            <span>没有符合条件的运行记录</span>
          </div>
        </div>
      </section>

      <section class="panel exec-detail-panel">
        <div v-if="detailLoading" class="detail-loading">
          <Loader2 :size="18" class="spin" /> 加载详情…
        </div>

        <template v-else-if="detail">
          <header class="detail-head">
            <div class="detail-title-wrap">
              <div class="detail-glyph" :class="statusTone(detail.status)">
                <Sparkles v-if="detail.kind === 'chat'" :size="18" />
                <GitBranch v-else :size="18" />
              </div>
              <div class="detail-title-copy">
                <div class="detail-kicker">
                  {{ detail.kind === 'scene' ? 'SCENE RUN' : 'CHAT RUN' }} · {{ detail.id }}
                </div>
                <h3 class="detail-title">{{ detail.title || detail.input || 'Agent 执行' }}</h3>
                <div class="detail-meta">
                  <span class="chip" :class="statusTone(detail.status) === 'good' ? 'mint' : statusTone(detail.status) === 'bad' ? 'rose' : statusTone(detail.status) === 'warn' ? 'amber' : 'neutral'">
                    {{ statusLabel(detail.status) }}
                  </span>
                  <span><Clock :size="10" /> {{ formatDateTime(detail.created_at) }}</span>
                  <span><Timer :size="10" /> {{ formatDuration(detail.duration_ms) }}</span>
                  <span v-if="detail.intent && (detail.intent as any).intent_type" class="detail-intent-type">
                    {{ intentTypeLabel[(detail.intent as any).intent_type] || (detail.intent as any).intent_type }}
                  </span>
                </div>
              </div>
            </div>
          </header>

          <div class="detail-scroll">
            <div v-if="detail.input" class="detail-input-block">
              <span class="detail-label">用户输入</span>
              <p>{{ detail.input }}</p>
            </div>

            <div v-if="intentInfo" class="detail-section">
              <div class="detail-section-head">
                <span><Sparkles :size="12" /> 意图解析</span>
                <em class="mono">{{ intentInfo.source }}</em>
              </div>
              <div class="intent-summary">
                <div class="intent-cell">
                  <span>意图标识</span>
                  <strong class="mono">{{ intentInfo.intent }}</strong>
                </div>
                <div class="intent-cell">
                  <span>置信度</span>
                  <strong>{{ Math.round((intentInfo.confidence || 0) * 100) }}%</strong>
                </div>
                <div class="intent-cell">
                  <span>解析来源</span>
                  <strong>{{ intentInfo.source }}</strong>
                </div>
                <div class="intent-cell">
                  <span>目标设备</span>
                  <strong>{{ (intentInfo.targets || []).length || '—' }}</strong>
                </div>
              </div>
              <div v-if="intentInfo.actions?.length" class="intent-action-list">
                <div v-for="(action, index) in intentInfo.actions" :key="index" class="intent-action-row">
                  <span class="action-index">{{ Number(index) + 1 }}</span>
                  <span class="action-label">{{ action.label || action.intent }}</span>
                  <span class="action-params mono">{{ compactArgs(action.params) }}</span>
                </div>
              </div>
            </div>

            <div v-if="timeline.length" class="detail-section">
              <div class="detail-section-head">
                <span><GitBranch :size="12" /> LangGraph 节点</span>
                <em class="mono">{{ timeline.length }} nodes</em>
              </div>
              <div class="detail-timeline">
                <div v-for="node in timeline" :key="node.key" class="detail-node">
                  <span class="detail-node-dot"></span>
                  <div class="detail-node-copy">
                    <div class="detail-node-top">
                      <span class="detail-node-label">{{ node.label }}</span>
                      <span class="detail-node-duration mono">{{ formatDuration(node.duration) }}</span>
                    </div>
                    <div v-if="node.summary" class="detail-node-summary">{{ node.summary }}</div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="toolCalls.length" class="detail-section">
              <div class="detail-section-head">
                <span><Wrench :size="12" /> Function Calling</span>
                <em class="mono">{{ toolCalls.length }} calls</em>
              </div>
              <div class="detail-tool-list">
                <div v-for="call in toolCalls" :key="call.id" class="detail-tool" :class="call.status">
                  <CheckCircle2 v-if="call.status === 'ok'" :size="12" />
                  <XCircle v-else-if="call.status === 'error'" :size="12" />
                  <Loader2 v-else :size="12" class="spin" />
                  <div class="detail-tool-copy">
                    <div class="detail-tool-top">
                      <span class="detail-tool-name">{{ call.label || call.name }}</span>
                      <span class="detail-tool-time mono">{{ formatDuration(call.duration) }}</span>
                    </div>
                    <div class="detail-tool-args mono">{{ compactArgs(call.args) }}</div>
                    <div v-if="call.message" class="detail-tool-msg">{{ call.message }}</div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="sceneEvents.length || sceneResult" class="detail-section">
              <div class="detail-section-head">
                <span><GitBranch :size="12" /> 场景编排过程</span>
                <em class="mono">{{ sceneResult?.status || '—' }}</em>
              </div>
              <div class="scene-trace">
                <div v-for="(event, index) in sceneEvents" :key="index" class="scene-event" :class="event.type">
                  <span class="scene-event-type">
                    {{ event.type === 'scene_start' ? '加载' : event.type === 'scene_condition' ? '条件' : event.type === 'scene_step_result' ? '动作' : event.type === 'scene_fallback' ? '兜底' : event.type === 'scene_step_skipped' ? '跳过' : '完成' }}
                  </span>
                  <span class="scene-event-text">
                    <template v-if="event.type === 'scene_start'">「{{ event.name }}」共 {{ event.total_steps }} 个动作</template>
                    <template v-else-if="event.type === 'scene_condition'">{{ event.passed ? '条件成立' : '条件不满足' }} · {{ event.reason }}</template>
                    <template v-else-if="event.type === 'scene_step_result'">{{ event.label }} · {{ event.ok ? event.message : event.message }}</template>
                    <template v-else-if="event.type === 'scene_step_skipped'">{{ event.label }} · {{ event.reason }}</template>
                    <template v-else-if="event.type === 'scene_fallback'">{{ event.success ? '兜底成功' : '兜底未完全成功' }}</template>
                    <template v-else-if="event.type === 'scene_done'">{{ event.result?.message }}</template>
                  </span>
                </div>
              </div>
            </div>

            <div v-if="responseText" class="detail-section">
              <div class="detail-section-head">
                <span><Sparkles :size="12" /> 最终回复</span>
              </div>
              <p class="detail-response">{{ responseText }}</p>
            </div>

            <div v-if="errorText" class="detail-error">
              <XCircle :size="12" />
              <span>{{ errorText }}</span>
            </div>

            <div v-if="!timeline.length && !toolCalls.length && !responseText && !errorText && !intentInfo" class="empty-state">
              <Activity :size="18" />
              <span>这条记录没有更多详情</span>
            </div>
          </div>
        </template>

        <div v-else class="detail-empty">
          <div class="empty-icon"><Activity :size="20" /></div>
          <span>选择左侧的一条运行记录查看详情</span>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.executions-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: calc(100dvh - var(--topbar-h) - 60px);
}

.exec-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel);
  overflow: hidden;
}

.exec-stat {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 15px 18px;
  border: none;
  border-radius: 0;
  background: transparent;
}

.exec-stat + .exec-stat {
  border-left: 1px solid var(--line);
}

.exec-stat-label {
  font-size: 10px;
  color: var(--text-3);
}

.exec-stat strong {
  font-family: var(--font-serif);
  font-size: 21px;
  font-weight: 500;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.exec-stat strong.good {
  color: var(--good);
}

.exec-stat strong.bad {
  color: var(--critical);
}

.exec-stat-note {
  margin-left: auto;
  font-size: 8.5px;
  color: var(--text-4);
}

.exec-layout {
  display: grid;
  grid-template-columns: minmax(300px, 400px) minmax(0, 1fr);
  gap: 14px;
  flex: 1;
  min-height: 0;
}

.exec-list-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 13px;
}

.exec-filters {
  display: flex;
  align-items: center;
  gap: 7px;
  justify-content: space-between;
}

.status-select {
  width: 102px;
  height: 30px;
  font-size: 10px;
  padding: 0 26px 0 9px;
  border-radius: 8px;
}

.exec-search {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  margin: 9px 0;
  padding: 0 9px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: rgba(41, 37, 36, 0.05);
  color: var(--text-4);
}

.exec-search input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  color: var(--text);
  font-size: 10.5px;
}

.exec-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin: 0 -4px;
  padding: 0 4px;
}

.exec-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 9px;
  border-radius: 9px;
  border: 1px solid transparent;
  background: transparent;
  text-align: left;
  transition: background 0.16s ease, border-color 0.16s ease;
}

.exec-row:hover {
  background: rgba(41, 37, 36, 0.028);
}

.exec-row.active {
  background: rgba(180, 74, 38, 0.045);
  border-color: rgba(180, 74, 38, 0.13);
}

.exec-status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex: 0 0 5px;
  background: var(--text-4);
}

.exec-status-dot.good {
  background: var(--good);
  box-shadow: 0 0 7px rgba(61, 122, 82, 0.25);
}

.exec-status-dot.warn {
  background: var(--warning);
}

.exec-status-dot.bad {
  background: var(--critical);
}

.exec-row-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.exec-row-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.exec-row-title {
  font-size: 11px;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.exec-row.active .exec-row-title {
  color: var(--text);
}

.exec-row-time {
  font-size: 8px;
  color: var(--text-4);
  white-space: nowrap;
}

.exec-row-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 8.5px;
  color: var(--text-4);
  white-space: nowrap;
}

.exec-kind {
  font-size: 7.5px;
  padding: 0 4px;
  border-radius: 3px;
  background: rgba(41, 37, 36, 0.04);
}

.exec-kind.scene {
  color: var(--indigo);
  background: var(--indigo-soft);
}

.exec-row-id {
  margin-left: auto;
  font-size: 7.5px;
  color: var(--text-4);
}

.exec-chevron {
  color: var(--text-4);
  opacity: 0;
  flex: 0 0 auto;
}

.exec-row:hover .exec-chevron,
.exec-row.active .exec-chevron {
  opacity: 1;
}

.exec-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 26px;
  font-size: 10.5px;
  color: var(--text-4);
}

.exec-detail-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.detail-loading,
.detail-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 9px;
  color: var(--text-4);
  font-size: 11px;
  padding: 40px;
}

.detail-head {
  padding: 17px 20px 13px;
  border-bottom: 1px solid var(--line);
}

.detail-title-wrap {
  display: flex;
  align-items: flex-start;
  gap: 11px;
}

.detail-glyph {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  border-radius: 11px;
  display: grid;
  place-items: center;
  color: var(--mint);
  background: var(--mint-soft);
  border: 1px solid rgba(180, 74, 38, 0.14);
}

.detail-glyph.bad {
  color: var(--critical);
  background: var(--critical-soft);
  border-color: rgba(168, 58, 50, 0.18);
}

.detail-glyph.warn {
  color: var(--warning);
  background: var(--amber-soft);
  border-color: rgba(169, 105, 28, 0.18);
}

.detail-title-copy {
  min-width: 0;
  flex: 1;
}

.detail-kicker {
  font-family: var(--font-mono);
  font-size: 7.5px;
  letter-spacing: 0.09em;
  color: var(--text-4);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-title {
  font-size: 16px;
  margin-top: 1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 6px;
  font-size: 8.5px;
  color: var(--text-4);
  flex-wrap: wrap;
}

.detail-meta > span {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.detail-intent-type {
  color: var(--indigo);
}

.detail-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.detail-input-block {
  padding: 10px 12px;
  border-radius: 9px;
  background: rgba(180, 74, 38, 0.035);
  border: 1px solid rgba(180, 74, 38, 0.09);
}

.detail-label {
  font-size: 8.5px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-4);
}

.detail-input-block p {
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--text);
  margin-top: 3px;
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--line);
  font-size: 9.5px;
  color: var(--text-3);
}

.detail-section-head span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.detail-section-head em {
  font-style: normal;
  font-size: 8px;
  color: var(--text-4);
  font-family: var(--font-mono);
}

.intent-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 7px;
}

.intent-cell {
  padding: 8px 9px;
  border-radius: 8px;
  border: 1px solid rgba(41, 37, 36, 0.07);
  background: rgba(41, 37, 36, 0.018);
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.intent-cell span {
  font-size: 8px;
  color: var(--text-4);
}

.intent-cell strong {
  font-size: 10.5px;
  color: var(--text-2);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.intent-action-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.intent-action-row {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 9.5px;
  color: var(--text-3);
}

.action-index {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  display: grid;
  place-items: center;
  font-size: 7.5px;
  font-family: var(--font-mono);
  color: var(--text-4);
  background: rgba(41, 37, 36, 0.04);
}

.action-label {
  color: var(--text-2);
}

.action-params {
  margin-left: auto;
  font-size: 8px;
  color: var(--text-4);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 55%;
}

.detail-timeline {
  display: flex;
  flex-direction: column;
  position: relative;
  padding-left: 3px;
}

.detail-node {
  display: flex;
  gap: 9px;
  padding-bottom: 9px;
  position: relative;
}

.detail-node:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 3px;
  top: 10px;
  bottom: 0;
  width: 1px;
  background: rgba(41, 37, 36, 0.09);
}

.detail-node-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  border: 1.5px solid var(--mint);
  background: #f7f2ea;
  flex: 0 0 7px;
  margin-top: 3px;
  z-index: 1;
}

.detail-node-copy {
  flex: 1;
  min-width: 0;
}

.detail-node-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.detail-node-label {
  font-size: 10px;
  color: var(--text-2);
}

.detail-node-duration {
  font-size: 8px;
  color: var(--text-4);
}

.detail-node-summary {
  font-size: 8.5px;
  color: var(--text-4);
  line-height: 1.5;
  margin-top: 1px;
}

.detail-tool-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.detail-tool {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  padding: 7px 8px;
  border-radius: 8px;
  border: 1px solid rgba(41, 37, 36, 0.06);
  background: rgba(41, 37, 36, 0.015);
  color: var(--text-4);
}

.detail-tool.ok {
  color: var(--good);
}

.detail-tool.error {
  color: var(--critical);
  border-color: rgba(168, 58, 50, 0.1);
  background: rgba(168, 58, 50, 0.025);
}

.detail-tool-copy {
  flex: 1;
  min-width: 0;
}

.detail-tool-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.detail-tool-name {
  font-size: 9.5px;
  color: var(--text-2);
}

.detail-tool-time {
  font-size: 8px;
  color: var(--text-4);
}

.detail-tool-args {
  font-size: 8px;
  color: var(--text-4);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-tool-msg {
  font-size: 8.5px;
  color: var(--text-3);
  margin-top: 2px;
  line-height: 1.45;
}

.scene-trace {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.scene-event {
  display: flex;
  gap: 7px;
  font-size: 8.5px;
  line-height: 1.5;
  color: var(--text-4);
}

.scene-event-type {
  flex: 0 0 26px;
  font-size: 7.5px;
  color: var(--text-3);
  border-left: 2px solid var(--line-strong);
  padding-left: 5px;
}

.scene-event.scene_step_result .scene-event-type {
  border-left-color: var(--mint);
}

.scene-event.scene_fallback .scene-event-type {
  border-left-color: var(--warning);
}

.scene-event-text {
  flex: 1;
  color: var(--text-3);
}

.detail-response {
  font-size: 11px;
  line-height: 1.7;
  color: var(--text-2);
  padding: 10px 12px;
  border-radius: 9px;
  background: rgba(41, 37, 36, 0.022);
  border: 1px solid var(--line);
  white-space: pre-wrap;
}

.detail-error {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 9px 11px;
  border-radius: 8px;
  border: 1px solid rgba(168, 58, 50, 0.16);
  background: rgba(168, 58, 50, 0.04);
  color: var(--critical);
  font-size: 9.5px;
  line-height: 1.55;
}

.spin {
  animation: spin 0.9s linear infinite;
}

@media (max-width: 1050px) {
  .exec-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .exec-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .exec-list-panel {
    max-height: 340px;
  }

  .exec-detail-panel {
    min-height: 460px;
  }
}

@media (max-width: 760px) {
  .executions-page {
    min-height: 0;
  }

  .exec-stats {
    gap: 8px;
  }

  .exec-stat {
    padding: 9px 10px;
  }

  .intent-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .exec-list-panel {
    max-height: 300px;
  }
}
</style>
