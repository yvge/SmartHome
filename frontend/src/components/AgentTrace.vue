<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  Brain,
  ChevronDown,
  Circle,
  Database,
  GitBranch,
  ListTree,
  Loader2,
  MessageSquareText,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Wrench,
  XCircle,
  CheckCircle2,
} from 'lucide-vue-next'
import type {
  AgentTraceNode,
  ParsedIntent,
  RetrievalPayload,
  SceneRunState,
  ToolTraceItem,
} from '@/types'
import { statusLabel } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    trace: AgentTraceNode[]
    intent?: ParsedIntent | null
    retrieval?: RetrievalPayload | null
    tools?: ToolTraceItem[]
    notes?: string[]
    scene?: SceneRunState | null
    streaming?: boolean
    defaultOpen?: boolean
  }>(),
  { trace: () => [], tools: () => [], notes: () => [], defaultOpen: false },
)

const open = ref(props.defaultOpen)

watch(
  () => props.defaultOpen,
  (value) => {
    if (value) open.value = true
  },
)

const intentTypeLabel: Record<string, string> = {
  control: '设备控制',
  query: '状态查询',
  scene: '场景执行',
  chat: '闲聊',
  knowledge: '知识问答',
  clarify: '澄清确认',
}

const nodeIcons: Record<string, any> = {
  understand: Brain,
  plan: ListTree,
  guard: ShieldCheck,
  execute: Sparkles,
  verify: ScanSearch,
  respond: MessageSquareText,
  scene: GitBranch,
  fallback: ShieldAlert,
  scene_load: GitBranch,
  scene_conditions: ShieldCheck,
  scene_plan: ListTree,
  scene_execute: Sparkles,
  scene_fallback: ShieldAlert,
  scene_verify: ScanSearch,
}

const durationTotal = computed(() =>
  Math.round(props.trace.reduce((sum, node) => sum + (node.duration_ms || 0), 0)),
)

const runningNode = computed(() => [...props.trace].reverse().find((node) => node.status === 'running'))

const topIntents = computed(() =>
  (props.retrieval?.intents || []).filter((hit) => hit.score >= 0.3).slice(0, 3),
)
const topKnowledge = computed(() =>
  (props.retrieval?.knowledge || []).filter((hit) => hit.score >= 0.32).slice(0, 2),
)
const confidence = computed(() => Math.round((props.intent?.confidence || 0) * 100))
const confidenceTone = computed(() => {
  if (!props.intent) return 'neutral'
  if (confidence.value >= 80) return 'good'
  if (confidence.value >= 60) return 'warn'
  return 'bad'
})

const actionLabels = computed(() =>
  (props.intent?.actions || []).map((action) => action.label || action.intent).filter(Boolean),
)

const sceneStepsDone = computed(
  () => props.scene?.steps.filter((step) => ['done', 'failed', 'skipped'].includes(step.status)).length || 0,
)

function toolLabel(name: string): string {
  const map: Record<string, string> = {
    control_light: '控制灯光',
    control_ac: '控制空调',
    control_curtain: '控制窗帘',
    control_purifier: '控制净化器',
    control_humidifier: '控制加湿器',
    control_socket: '控制插座',
    control_speaker: '控制音箱',
    control_vacuum: '控制扫地机',
    query_device: '查询设备状态',
    query_environment: '查询环境',
  }
  return map[name] || name
}

function scoreWidth(score: number): string {
  return `${Math.max(4, Math.min(100, Math.round(score * 100)))}%`
}

function compactArgs(args: Record<string, any>): string {
  return Object.entries(args)
    .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join(' · ')
}
</script>

<template>
  <div class="agent-trace" :class="{ open, live: streaming }">
    <button class="trace-head" type="button" @click="open = !open">
      <span class="trace-spark">
        <Sparkles :size="12" />
      </span>
      <span class="trace-title">思考与执行轨迹</span>
      <span v-if="intent" class="trace-tag" :class="confidenceTone">
        {{ intentTypeLabel[intent.intent_type] || intent.intent_type }} · {{ confidence }}%
      </span>
      <span v-if="retrieval" class="trace-meta mono">
        RAG {{ retrieval.latency_ms.toFixed(0) }}ms · {{ trace.length }} nodes
      </span>
      <span v-if="streaming && runningNode" class="trace-running">
        <Loader2 :size="11" class="spin" /> {{ runningNode.label }}
      </span>
      <ChevronDown :size="13" class="trace-chevron" :class="{ flipped: open }" />
    </button>

    <Transition name="trace-expand">
      <div v-if="open" class="trace-body">
        <div v-if="notes.length" class="trace-notes">
          <div v-for="(note, index) in notes" :key="index">{{ note }}</div>
        </div>

        <div class="trace-grid">
          <section v-if="retrieval" class="trace-section retrieval-section">
            <div class="trace-section-head">
              <span><Database :size="11" /> RAG 召回</span>
              <em class="mono">{{ retrieval.backend }} · {{ retrieval.latency_ms.toFixed(1) }}ms</em>
            </div>
            <div class="hit-list">
              <div v-for="hit in [...topIntents, ...topKnowledge]" :key="hit.id" class="hit">
                <div class="hit-top">
                  <span class="hit-kind" :class="hit.kind">{{ hit.kind === 'intent' ? '意图' : '知识' }}</span>
                  <span class="hit-text">{{ hit.text }}</span>
                  <span class="hit-score mono">{{ Math.round(hit.score * 100) }}%</span>
                </div>
                <div class="hit-bar"><span :style="{ width: scoreWidth(hit.score) }"></span></div>
              </div>
              <div v-if="!topIntents.length && !topKnowledge.length" class="trace-empty">没有召回到相关片段</div>
            </div>
          </section>

          <section v-if="intent" class="trace-section intent-section">
            <div class="trace-section-head">
              <span><Brain :size="11" /> 意图解析</span>
              <em class="mono">{{ intent.source }}</em>
            </div>
            <div class="intent-row">
              <span class="intent-type">{{ intentTypeLabel[intent.intent_type] || intent.intent_type }}</span>
              <span class="intent-name mono">{{ intent.intent }}</span>
              <span class="intent-conf" :class="confidenceTone">{{ confidence }}%</span>
            </div>
            <div v-if="actionLabels.length" class="intent-actions">
              <span v-for="(label, index) in actionLabels" :key="index" class="action-pill">{{ label }}</span>
            </div>
            <div v-else-if="intent.clarify" class="intent-clarify">{{ intent.clarify }}</div>
          </section>
        </div>

        <section v-if="trace.length" class="trace-section">
          <div class="trace-section-head">
            <span><GitBranch :size="11" /> LangGraph 节点</span>
            <em class="mono">total {{ durationTotal }}ms</em>
          </div>
          <div class="node-timeline">
            <div v-for="(node, index) in trace" :key="node.key" class="node" :class="node.status">
              <div class="node-rail">
                <component
                  :is="node.status === 'running' ? Loader2 : (nodeIcons[node.node] || Circle)"
                  :size="12"
                  :class="{ spin: node.status === 'running' }"
                />
                <span v-if="index < trace.length - 1" class="node-line"></span>
              </div>
              <div class="node-content">
                <div class="node-top">
                  <span class="node-label">{{ node.label }}</span>
                  <span v-if="node.duration_ms" class="node-duration mono">{{ node.duration_ms.toFixed(0) }}ms</span>
                </div>
                <div v-if="node.summary" class="node-summary">{{ node.summary }}</div>
              </div>
            </div>
          </div>
        </section>

        <section v-if="tools.length" class="trace-section">
          <div class="trace-section-head">
            <span><Wrench :size="11" /> Function Calling</span>
            <em class="mono">{{ tools.length }} calls</em>
          </div>
          <div class="tool-list">
            <div v-for="tool in tools" :key="tool.callId" class="tool" :class="tool.status">
              <div class="tool-top">
                <span class="tool-status">
                  <Loader2 v-if="tool.status === 'running'" :size="11" class="spin" />
                  <CheckCircle2 v-else-if="tool.status === 'ok'" :size="11" />
                  <XCircle v-else :size="11" />
                </span>
                <span class="tool-name">{{ toolLabel(tool.name) }}</span>
                <span class="tool-id mono">{{ tool.name }}</span>
                <span v-if="tool.duration_ms" class="tool-time mono">{{ tool.duration_ms.toFixed(0) }}ms</span>
              </div>
              <div class="tool-args mono">{{ compactArgs(tool.args) || '—' }}</div>
              <div v-if="tool.message" class="tool-result">{{ tool.message }}</div>
            </div>
          </div>
        </section>

        <section v-if="scene" class="trace-section">
          <div class="trace-section-head">
            <span><GitBranch :size="11" /> 场景执行 · {{ scene.name }}</span>
            <em class="mono">{{ sceneStepsDone }}/{{ scene.steps.length }}</em>
          </div>
          <div class="scene-inline">
            <div v-if="scene.condition" class="scene-cond" :class="{ passed: scene.condition.passed }">
              {{ scene.condition.reason }}
            </div>
            <div class="scene-step-list">
              <div v-for="step in scene.steps" :key="step.index" class="scene-step" :class="step.status">
                <span class="scene-step-dot"></span>
                <span class="scene-step-label">{{ step.label }}</span>
                <span class="scene-step-status">{{ statusLabel(step.status) }}</span>
              </div>
            </div>
            <div v-if="scene.fallback" class="scene-fallback-line">
              {{ scene.fallback.success ? '异常兜底已生效' : '已尝试兜底' }}
            </div>
          </div>
        </section>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.agent-trace {
  border: 1px solid rgba(148, 178, 209, 0.1);
  border-radius: 12px;
  background: rgba(5, 11, 18, 0.34);
  overflow: hidden;
}

.agent-trace.live {
  border-color: rgba(94, 234, 212, 0.14);
}

.trace-head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  background: transparent;
  text-align: left;
  color: var(--text-3);
}

.trace-head:hover {
  background: rgba(255, 255, 255, 0.02);
}

.trace-spark {
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  border-radius: 7px;
  display: grid;
  place-items: center;
  color: var(--mint);
  background: var(--mint-soft);
}

.trace-title {
  font-size: 10.5px;
  font-weight: 500;
  color: var(--text-2);
  white-space: nowrap;
}

.trace-tag {
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-3);
  white-space: nowrap;
}

.trace-tag.good {
  color: var(--mint);
  background: var(--mint-soft);
}

.trace-tag.warn {
  color: var(--warning);
  background: var(--amber-soft);
}

.trace-tag.bad {
  color: var(--critical);
  background: var(--critical-soft);
}

.trace-meta {
  font-size: 8.5px;
  color: var(--text-4);
  white-space: nowrap;
}

.trace-running {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 9px;
  color: var(--mint);
  white-space: nowrap;
}

.trace-chevron {
  margin-left: auto;
  color: var(--text-4);
  transition: transform 0.2s ease;
  flex: 0 0 auto;
}

.trace-chevron.flipped {
  transform: rotate(180deg);
}

.trace-body {
  padding: 2px 10px 11px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.trace-notes {
  font-size: 9.5px;
  color: var(--warning);
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(244, 195, 95, 0.05);
  border: 1px solid rgba(244, 195, 95, 0.12);
}

.trace-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.trace-section {
  border: 1px solid rgba(148, 178, 209, 0.075);
  border-radius: 9px;
  padding: 8px 9px;
  background: rgba(255, 255, 255, 0.015);
  min-width: 0;
}

.trace-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 7px;
  font-size: 9px;
  color: var(--text-3);
  letter-spacing: 0.04em;
}

.trace-section-head span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.trace-section-head em {
  font-style: normal;
  font-size: 8px;
  color: var(--text-4);
  white-space: nowrap;
}

.hit-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.hit-top {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.hit-kind {
  flex: 0 0 auto;
  font-size: 7.5px;
  padding: 1px 4px;
  border-radius: 3px;
  color: var(--indigo);
  background: var(--indigo-soft);
}

.hit-kind.knowledge {
  color: var(--amber);
  background: var(--amber-soft);
}

.hit-text {
  font-size: 9px;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.hit-score {
  font-size: 8px;
  color: var(--text-4);
    flex: 0 0 auto;
}

.hit-bar {
  height: 2px;
  border-radius: 99px;
  background: rgba(255, 255, 255, 0.055);
  overflow: hidden;
  margin-top: 2px;
}

.hit-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: color-mix(in srgb, var(--mint) 65%, transparent);
}

.hit-kind.knowledge {
  --hit-color: var(--amber);
}

.trace-empty {
  font-size: 9px;
  color: var(--text-4);
  padding: 4px 0;
}

.intent-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.intent-type {
  font-size: 10px;
  color: var(--text);
  font-weight: 500;
}

.intent-name {
  font-size: 8.5px;
  color: var(--text-4);
  background: rgba(255, 255, 255, 0.03);
  padding: 2px 5px;
  border-radius: 4px;
}

.intent-conf {
  font-size: 9px;
  color: var(--text-3);
  margin-left: auto;
  font-variant-numeric: tabular-nums;
}

.intent-conf.good {
  color: var(--mint);
}

.intent-conf.warn {
  color: var(--warning);
}

.intent-conf.bad {
  color: var(--critical);
}

.intent-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.action-pill {
  font-size: 8.5px;
  color: var(--text-2);
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(94, 234, 212, 0.05);
  border: 1px solid rgba(94, 234, 212, 0.08);
}

.intent-clarify {
  margin-top: 5px;
  font-size: 9px;
  color: var(--warning);
}

.node-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.node {
  display: flex;
  gap: 7px;
  min-height: 26px;
}

.node-rail {
  flex: 0 0 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  color: var(--text-4);
  padding-top: 2px;
}

.node.done .node-rail {
  color: var(--mint);
}

.node.running .node-rail {
  color: var(--mint);
}

.node-line {
  width: 1px;
  flex: 1;
  background: rgba(148, 178, 209, 0.1);
  margin: 2px 0;
}

.node-content {
  flex: 1;
  min-width: 0;
  padding-bottom: 7px;
}

.node-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.node-label {
  font-size: 9.5px;
  color: var(--text-2);
}

.node.done .node-label {
  color: var(--text);
}

.node-duration {
  font-size: 8px;
  color: var(--text-4);
}

.node-summary {
  font-size: 8.5px;
  color: var(--text-4);
  margin-top: 1px;
  line-height: 1.45;
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.tool {
  padding: 6px 7px;
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.018);
  border: 1px solid rgba(148, 178, 209, 0.06);
}

.tool-top {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.tool-status {
  color: var(--text-4);
  flex: 0 0 auto;
}

.tool.ok .tool-status {
  color: var(--good);
}

.tool.error .tool-status {
  color: var(--critical);
}

.tool.running .tool-status {
  color: var(--mint);
}

.tool-name {
  font-size: 9px;
  color: var(--text-2);
}

.tool-id {
  font-size: 7.5px;
  color: var(--text-4);
  margin-left: auto;
}

.tool-time {
  font-size: 7.5px;
  color: var(--text-4);
}

.tool-args {
  font-size: 8px;
  color: var(--text-4);
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-result {
  font-size: 8.5px;
  color: var(--text-3);
  margin-top: 2px;
  line-height: 1.45;
}

.scene-inline {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.scene-cond {
  font-size: 8.5px;
  color: var(--text-3);
  padding: 4px 6px;
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.02);
}

.scene-cond.passed {
  color: var(--mint);
  background: var(--mint-soft);
}

.scene-step-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.scene-step {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 8.5px;
  color: var(--text-3);
}

.scene-step-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--text-4);
  flex: 0 0 4px;
}

.scene-step.done .scene-step-dot {
  background: var(--good);
}

.scene-step.failed .scene-step-dot {
  background: var(--critical);
}

.scene-step.running .scene-step-dot {
  background: var(--mint);
  animation: pulse-soft 1.2s infinite;
}

.scene-step-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scene-step-status {
  margin-left: auto;
  color: var(--text-4);
  font-size: 8px;
  white-space: nowrap;
}

.scene-fallback-line {
  font-size: 8px;
  color: var(--warning);
}

.spin {
  animation: spin 0.9s linear infinite;
}

.trace-expand-enter-active,
.trace-expand-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.trace-expand-enter-from,
.trace-expand-leave-to {
  opacity: 0;
  transform: translateY(-3px);
}

@media (max-width: 760px) {
  .trace-grid {
    grid-template-columns: 1fr;
  }

  .trace-meta {
    display: none;
  }
}
</style>
