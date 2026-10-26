<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  CheckCircle2,
  Circle,
  Loader2,
  MinusCircle,
  ShieldAlert,
  Square,
  X,
  XCircle,
  Zap,
} from 'lucide-vue-next'
import DeviceIcon from '@/components/DeviceIcon.vue'
import { useSceneStore } from '@/stores/scenes'
import { statusLabel } from '@/utils/format'

const scenes = useSceneStore()
const run = computed(() => scenes.activeRun)
const now = ref(Date.now())
let timer: number | undefined

watch(
  () => scenes.activeRun,
  (value) => {
    if (value) {
      now.value = Date.now()
      if (!timer) {
        timer = window.setInterval(() => {
          now.value = Date.now()
        }, 500)
      }
    } else if (timer) {
      window.clearInterval(timer)
      timer = undefined
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})

const elapsed = computed(() => {
  if (!run.value) return '0.0'
  const end = run.value.finishedAt || now.value
  return ((end - run.value.startedAt) / 1000).toFixed(1)
})

const completedCount = computed(() => {
  if (!run.value) return 0
  return run.value.steps.filter((step) => ['done', 'failed', 'skipped'].includes(step.status)).length
})

const progress = computed(() => {
  if (!run.value || !run.value.steps.length) return 0
  return Math.round((completedCount.value / run.value.steps.length) * 100)
})

const statusClass = computed(() => {
  const status = run.value?.status
  if (status === 'success') return 'success'
  if (status === 'partial') return 'warning'
  if (status === 'failed') return 'failed'
  if (status === 'skipped') return 'neutral'
  return 'running'
})

function iconFor(status: string) {
  if (status === 'done') return CheckCircle2
  if (status === 'failed') return XCircle
  if (status === 'skipped') return MinusCircle
  if (status === 'running') return Loader2
  return Circle
}

function close() {
  if (run.value?.status === 'running') {
    scenes.stopScene()
  }
  scenes.closeRun()
}
</script>

<template>
  <Teleport to="body">
    <Transition name="scene-overlay">
      <div v-if="run" class="scene-backdrop" @click.self="close">
        <div class="scene-panel panel" role="dialog" aria-modal="true" :aria-label="`${run.name}执行状态`">
          <header class="scene-head">
            <div class="scene-title-wrap">
              <div class="scene-icon" :class="statusClass">
                <DeviceIcon :icon="run.icon" :size="23" />
              </div>
              <div>
                <div class="scene-eyebrow">SCENE ORCHESTRATION</div>
                <h3 class="scene-name">{{ run.name }}</h3>
                <p v-if="run.description" class="scene-desc">{{ run.description }}</p>
              </div>
            </div>
            <div class="scene-head-right">
              <span class="chip" :class="statusClass === 'success' ? 'mint' : statusClass === 'failed' ? 'rose' : statusClass === 'warning' ? 'amber' : 'indigo'">
                <span v-if="run.status === 'running'" class="pulse-dot"></span>
                {{ statusLabel(run.status) }}
              </span>
              <button class="icon-btn sm" aria-label="关闭" @click="close">
                <X :size="14" />
              </button>
            </div>
          </header>

          <div class="scene-meta-row">
            <span class="meta-item"><Zap :size="11" /> 用时 {{ elapsed }}s</span>
            <span class="meta-item">{{ completedCount }} / {{ run.steps.length }} 个动作</span>
            <span v-if="run.condition" class="meta-item" :class="{ pass: run.condition.passed }">
              {{ run.condition.passed ? '条件成立' : run.condition.optional ? '可选条件未满足' : '条件未满足' }}
            </span>
          </div>

          <div class="progress-track">
            <div class="progress-fill" :class="statusClass" :style="{ width: `${progress}%` }"></div>
          </div>

          <div v-if="run.condition" class="condition-card" :class="{ passed: run.condition.passed, optional: run.condition.optional }">
            <ShieldAlert :size="14" />
            <div>
              <div class="condition-title">条件判断</div>
              <div class="condition-reason">{{ run.condition.reason }}</div>
            </div>
          </div>

          <div class="step-list">
            <div
              v-for="step in run.steps"
              :key="step.index"
              class="step"
              :class="step.status"
            >
              <div class="step-rail">
                <component
                  :is="iconFor(step.status)"
                  :size="15"
                  :class="{ spin: step.status === 'running' }"
                />
              </div>
              <div class="step-content">
                <div class="step-top">
                  <span class="step-label">{{ step.label }}</span>
                  <span class="step-status">{{ statusLabel(step.status) }}</span>
                </div>
                <div v-if="step.message" class="step-message">{{ step.message }}</div>
              </div>
            </div>
            <div v-if="!run.steps.length" class="step-empty">正在加载场景动作…</div>
          </div>

          <div v-if="run.fallback" class="fallback-card" :class="{ ok: run.fallback.success }">
            <div class="fallback-title">
              <ShieldAlert :size="13" />
              异常兜底{{ run.fallback.success ? '已生效' : '尝试完成' }}
            </div>
            <div v-for="(item, index) in run.fallback.results" :key="index" class="fallback-item">
              <CheckCircle2 v-if="item.ok" :size="12" />
              <XCircle v-else :size="12" />
              <span>{{ item.message }}</span>
            </div>
          </div>

          <div v-if="run.message" class="scene-message">
            {{ run.message }}
          </div>

          <footer class="scene-actions">
            <button v-if="run.status === 'running'" class="btn btn-sm btn-danger" @click="scenes.stopScene()">
              <Square :size="12" /> 停止执行
            </button>
            <button v-else class="btn btn-sm btn-primary" @click="close">
              完成
            </button>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.scene-backdrop {
  position: fixed;
  inset: 0;
  z-index: 330;
  display: grid;
  place-items: center;
  padding: 22px;
  background: rgba(33, 29, 25, 0.34);
  backdrop-filter: blur(8px);
}

.scene-panel {
  width: min(590px, 100%);
  max-height: min(82vh, 780px);
  display: flex;
  flex-direction: column;
  padding: 22px;
  background: #f7f2ea;
  border-color: var(--line-strong);
}

.scene-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.scene-title-wrap {
  display: flex;
  align-items: flex-start;
  gap: 13px;
  min-width: 0;
}

.scene-icon {
  width: 50px;
  height: 50px;
  flex: 0 0 50px;
  border-radius: 15px;
  display: grid;
  place-items: center;
  background: var(--mint-soft);
  border: 1px solid rgba(180, 74, 38, 0.18);
  color: var(--mint);
}

.scene-icon.failed {
  color: var(--critical);
  background: var(--critical-soft);
  border-color: rgba(168, 58, 50, 0.2);
}

.scene-icon.warning {
  color: var(--warning);
  background: var(--amber-soft);
  border-color: rgba(169, 105, 28, 0.2);
}

.scene-icon.neutral {
  color: var(--text-2);
  background: rgba(41, 37, 36, 0.04);
  border-color: var(--line);
}

.scene-eyebrow {
  font-size: 8.5px;
  font-family: var(--font-mono);
  letter-spacing: 0.18em;
  color: var(--text-4);
}

.scene-name {
  font-size: 20px;
  margin-top: 2px;
}

.scene-desc {
  font-size: 11px;
  color: var(--text-3);
  margin-top: 2px;
}

.scene-head-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
}

.pulse-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse-soft 1.2s ease infinite;
}

.scene-meta-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
  color: var(--text-3);
  font-size: 10px;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-variant-numeric: tabular-nums;
}

.meta-item.pass {
  color: var(--mint);
}

.progress-track {
  height: 3px;
  border-radius: 99px;
  background: rgba(41, 37, 36, 0.07);
  margin: 11px 0 16px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--mint), #a3421f);
  transition: width 0.4s ease;
}

.progress-fill.warning {
  background: linear-gradient(90deg, var(--warning), var(--serious));
}

.progress-fill.failed {
  background: linear-gradient(90deg, var(--critical), #a83a32);
}

.condition-card {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(169, 105, 28, 0.16);
  background: rgba(169, 105, 28, 0.045);
  color: var(--warning);
  margin-bottom: 14px;
}

.condition-card.passed {
  border-color: rgba(180, 74, 38, 0.15);
  background: rgba(180, 74, 38, 0.04);
  color: var(--mint);
}

.condition-card.optional:not(.passed) {
  color: var(--text-2);
  border-color: var(--line);
  background: rgba(41, 37, 36, 0.025);
}

.condition-title {
  font-size: 10px;
  font-weight: 550;
  letter-spacing: 0.08em;
}

.condition-reason {
  font-size: 10.5px;
  color: var(--text-3);
  margin-top: 2px;
  line-height: 1.5;
}

.step-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 2px -6px 0;
  padding: 0 6px;
}

.step {
  display: flex;
  gap: 10px;
  padding: 8px 6px;
  border-radius: 8px;
  transition: background 0.2s ease;
}

.step.running {
  background: rgba(180, 74, 38, 0.035);
}

.step-rail {
  flex: 0 0 20px;
  display: flex;
  justify-content: center;
  padding-top: 1px;
  color: var(--text-4);
  position: relative;
}

.step.done .step-rail {
  color: var(--good);
}

.step.failed .step-rail {
  color: var(--critical);
}

.step.skipped .step-rail {
  color: var(--text-4);
}

.step.running .step-rail {
  color: var(--mint);
}

.step-content {
  flex: 1;
  min-width: 0;
}

.step-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.step-label {
  font-size: 11.5px;
  color: var(--text-2);
}

.step.done .step-label {
  color: var(--text);
}

.step-status {
  font-size: 9px;
  color: var(--text-4);
  white-space: nowrap;
}

.step-message {
  font-size: 9.5px;
  color: var(--text-4);
  margin-top: 1px;
  line-height: 1.5;
}

.step-empty {
  padding: 18px;
  text-align: center;
  font-size: 11px;
  color: var(--text-4);
}

.fallback-card {
  margin-top: 14px;
  padding: 11px 12px;
  border-radius: 10px;
  border: 1px solid rgba(168, 58, 50, 0.16);
  background: rgba(168, 58, 50, 0.045);
}

.fallback-card.ok {
  border-color: rgba(180, 74, 38, 0.15);
  background: rgba(180, 74, 38, 0.04);
}

.fallback-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  font-weight: 550;
  color: var(--warning);
  margin-bottom: 5px;
}

.fallback-card.ok .fallback-title {
  color: var(--mint);
}

.fallback-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 10px;
  color: var(--text-3);
  line-height: 1.5;
}

.fallback-item + .fallback-item {
  margin-top: 3px;
}

.scene-message {
  margin-top: 14px;
  padding: 12px 13px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(41, 37, 36, 0.025);
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--text-2);
}

.scene-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.spin {
  animation: spin 0.9s linear infinite;
}

.scene-overlay-enter-active,
.scene-overlay-leave-active {
  transition: opacity 0.22s ease;
}

.scene-overlay-enter-active .scene-panel,
.scene-overlay-leave-active .scene-panel {
  transition: transform 0.24s cubic-bezier(0.2, 0.8, 0.3, 1), opacity 0.22s ease;
}

.scene-overlay-enter-from,
.scene-overlay-leave-to {
  opacity: 0;
}

.scene-overlay-enter-from .scene-panel,
.scene-overlay-leave-to .scene-panel {
  transform: translateY(12px) scale(0.985);
  opacity: 0;
}
</style>
