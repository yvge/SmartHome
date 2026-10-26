<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  ChevronDown,
  Clock,
  Copy,
  GitBranch,
  Layers,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Thermometer,
  Trash2,
  Workflow,
} from 'lucide-vue-next'
import DeviceIcon from '@/components/DeviceIcon.vue'
import SceneEditor from '@/components/SceneEditor.vue'
import { useSceneStore } from '@/stores/scenes'
import { useHomeStore } from '@/stores/home'
import { useUiStore } from '@/stores/ui'
import type { Scene } from '@/types'

const sceneStore = useSceneStore()
const home = useHomeStore()
const ui = useUiStore()

const editorOpen = ref(false)
const editingScene = ref<Scene | null>(null)
const expanded = ref<Record<string, boolean>>({})
const runningId = computed(() => sceneStore.runningSceneId)

const builtinScenes = computed(() => sceneStore.builtinScenes)
const customScenes = computed(() => sceneStore.customScenes)

const flowNodes = [
  { key: 'load', label: '加载场景', icon: Layers },
  { key: 'conditions', label: '条件判断', icon: GitBranch },
  { key: 'plan', label: '动作编排', icon: Workflow },
  { key: 'execute', label: '设备联动', icon: Sparkles },
  { key: 'fallback', label: '异常兜底', icon: ShieldAlert },
  { key: 'verify', label: '状态校验', icon: RefreshCw },
]

function conditionChip(scene: Scene): { text: string; icon: any; tone: string } | null {
  const condition = scene.condition
  if (!condition) return null
  if (condition.type === 'time') {
    const value = Array.isArray(condition.value) ? condition.value : []
    return { text: `${value[0]}–${value[1]}`, icon: Clock, tone: 'indigo' }
  }
  if (condition.type === 'temperature') {
    return { text: `温度 ${condition.op} ${condition.value}°C`, icon: Thermometer, tone: 'amber' }
  }
  if (condition.type === 'humidity') {
    return { text: `湿度 ${condition.op} ${condition.value}%`, icon: Thermometer, tone: 'mint' }
  }
  return { text: '设备条件', icon: GitBranch, tone: 'neutral' }
}

function stepsOf(scene: Scene) {
  return scene.steps.slice(0, 4)
}

function stepText(step: Scene['steps'][number]): string {
  const params = Object.entries(step.params || {})
    .map(([key, value]) => {
      const map: Record<string, string> = {
        power: value ? '开' : '关',
        brightness: `亮度${value}%`,
        color_temp: `${value}K`,
        target_temp: `${value}°C`,
        position: `开合${value}%`,
        mode: `模式${value}`,
        target_humidity: `湿度${value}%`,
        volume: `音量${value}`,
      }
      return map[key] || `${key}=${value}`
    })
    .join(' · ')
  return params
}

function deviceName(deviceId: string): string {
  return home.devices.find((device) => device.id === deviceId)?.name || deviceId
}

function runScene(scene: Scene) {
  sceneStore.runScene(scene)
}

function toggleExpand(sceneId: string) {
  expanded.value = { ...expanded.value, [sceneId]: !expanded.value[sceneId] }
}

function openCreate() {
  editingScene.value = null
  editorOpen.value = true
}

function openEdit(scene: Scene) {
  if (scene.builtin) {
    ui.info('内置场景不可编辑，可先复制一份再修改')
    return
  }
  editingScene.value = scene
  editorOpen.value = true
}

async function handleSave(payload: Record<string, unknown>) {
  const result = editingScene.value
    ? await sceneStore.updateScene(editingScene.value.id, payload)
    : await sceneStore.createScene(payload)
  if (result) {
    editorOpen.value = false
    editingScene.value = null
  }
}

async function duplicate(scene: Scene) {
  const copy = await sceneStore.duplicateScene(scene.id)
  if (copy) {
    editingScene.value = copy
    editorOpen.value = true
  }
}

async function remove(scene: Scene) {
  await sceneStore.deleteScene(scene.id)
}

const totalSteps = computed(() =>
  sceneStore.scenes.reduce((sum, scene) => sum + scene.steps.length, 0),
)
const withConditions = computed(() => sceneStore.scenes.filter((scene) => scene.condition).length)
const withFallback = computed(() => sceneStore.scenes.filter((scene) => scene.fallback.length).length)
</script>

<template>
  <div class="page scenes-page">
    <section class="page-head">
      <div>
        <div class="eyebrow">日常自动化</div>
        <h1>场景编排</h1>
        <p class="lede">
          把一句话拆成几步：先看条件，再依次调用设备；某个环节出问题时，自动走备用方案。
          运行时会逐步展示每个节点的结果。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" @click="sceneStore.fetchScenes()">
          <RefreshCw :size="14" />
          刷新
        </button>
        <button class="btn btn-primary" @click="openCreate">
          <Plus :size="14" />
          新建场景
        </button>
      </div>
    </section>

    <section class="flow-strip panel">
      <div class="flow-head">
        <div>
          <div class="panel-kicker">执行路径</div>
          <div class="flow-title">多步场景执行图</div>
        </div>
        <span class="chip mint"><span class="chip-dot"></span>LangGraph 流程</span>
      </div>
      <div class="flow-track">
        <div v-for="(node, index) in flowNodes" :key="node.key" class="flow-node-wrap">
          <div class="flow-node" :class="{ fallback: node.key === 'fallback' }">
            <component :is="node.icon" :size="13" />
            <span>{{ node.label }}</span>
          </div>
          <span v-if="index < flowNodes.length - 1" class="flow-arrow">→</span>
        </div>
        <div class="flow-loop">
          <span class="loop-line"></span>
          <span class="loop-label">按动作逐步执行</span>
        </div>
      </div>
      <div class="flow-stats">
        <div><strong>{{ sceneStore.scenes.length }}</strong><span>场景</span></div>
        <div><strong>{{ totalSteps }}</strong><span>动作节点</span></div>
        <div><strong>{{ withConditions }}</strong><span>带条件</span></div>
        <div><strong>{{ withFallback }}</strong><span>含兜底</span></div>
      </div>
    </section>

    <section class="scene-section">
      <header class="section-head">
        <div class="section-title">
          <Sparkles :size="14" />
          内置场景
          <span class="section-count">{{ builtinScenes.length }}</span>
        </div>
        <span class="section-note">内置场景不可直接修改，可复制后自定义</span>
      </header>

      <div v-if="sceneStore.loading" class="scene-grid">
        <div v-for="index in 6" :key="index" class="skeleton scene-skeleton"></div>
      </div>

      <div v-else class="scene-grid">
        <article
          v-for="scene in builtinScenes"
          :key="scene.id"
          class="scene-card panel"
          :class="{ running: runningId === scene.id }"
        >
          <div class="scene-card-head">
            <div class="scene-glyph">
              <DeviceIcon :icon="scene.icon" :size="21" />
            </div>
            <div class="scene-title-copy">
              <div class="scene-name">{{ scene.name }}</div>
              <div class="scene-desc">{{ scene.description }}</div>
            </div>
            <span class="scene-step-badge">{{ scene.steps.length }} 步</span>
          </div>

          <div class="scene-tags">
            <span
              v-if="conditionChip(scene)"
              class="chip"
              :class="conditionChip(scene)!.tone"
            >
              <component :is="conditionChip(scene)!.icon" :size="10" />
              {{ conditionChip(scene)!.text }}
            </span>
            <span v-if="scene.fallback.length" class="chip amber">
              <ShieldAlert :size="10" />
              兜底 {{ scene.fallback.length }}
            </span>
            <span v-if="scene.condition?.optional" class="chip neutral">可选条件</span>
          </div>

          <button class="steps-toggle" @click="toggleExpand(scene.id)">
            查看动作序列
            <ChevronDown :size="12" :class="{ flipped: expanded[scene.id] }" />
          </button>

          <Transition name="fade">
            <ol v-if="expanded[scene.id]" class="step-preview">
              <li v-for="(step, index) in scene.steps" :key="index">
                <span class="step-index">{{ index + 1 }}</span>
                <div class="step-copy">
                  <span class="step-device">{{ deviceName(step.device_id) }}</span>
                  <span class="step-params">{{ stepText(step) }}</span>
                </div>
                <span v-if="step.critical" class="step-critical">关键</span>
              </li>
            </ol>
          </Transition>

          <div class="scene-card-foot">
            <button class="btn btn-sm btn-ghost" title="复制场景" @click="duplicate(scene)">
              <Copy :size="12" />
              复制
            </button>
            <button
              class="btn btn-sm btn-primary run-btn"
              :disabled="Boolean(runningId)"
              @click="runScene(scene)"
            >
              <Play :size="12" />
              {{ runningId === scene.id ? '执行中…' : '执行场景' }}
            </button>
          </div>
        </article>
      </div>
    </section>

    <section class="scene-section">
      <header class="section-head">
        <div class="section-title">
          <Workflow :size="14" />
          自定义场景
          <span class="section-count">{{ customScenes.length }}</span>
        </div>
        <span class="section-note">由你编排，可随时编辑、复制或删除</span>
      </header>

      <div v-if="customScenes.length" class="scene-grid">
        <article
          v-for="scene in customScenes"
          :key="scene.id"
          class="scene-card panel custom"
          :class="{ running: runningId === scene.id }"
        >
          <div class="scene-card-head">
            <div class="scene-glyph custom">
              <DeviceIcon :icon="scene.icon" :size="21" />
            </div>
            <div class="scene-title-copy">
              <div class="scene-name">
                {{ scene.name }}
                <span class="custom-badge">自定义</span>
              </div>
              <div class="scene-desc">{{ scene.description || '未填写描述' }}</div>
            </div>
            <span class="scene-step-badge">{{ scene.steps.length }} 步</span>
          </div>

          <div class="scene-tags">
            <span v-if="conditionChip(scene)" class="chip" :class="conditionChip(scene)!.tone">
              <component :is="conditionChip(scene)!.icon" :size="10" />
              {{ conditionChip(scene)!.text }}
            </span>
            <span v-if="scene.fallback.length" class="chip amber">
              <ShieldAlert :size="10" />
              兜底 {{ scene.fallback.length }}
            </span>
            <span class="chip neutral"><Layers :size="10" /> {{ scene.steps.length }} 个动作</span>
          </div>

          <button class="steps-toggle" @click="toggleExpand(scene.id)">
            查看动作序列
            <ChevronDown :size="12" :class="{ flipped: expanded[scene.id] }" />
          </button>

          <Transition name="fade">
            <ol v-if="expanded[scene.id]" class="step-preview">
              <li v-for="(step, index) in scene.steps" :key="index">
                <span class="step-index">{{ index + 1 }}</span>
                <div class="step-copy">
                  <span class="step-device">{{ deviceName(step.device_id) }}</span>
                  <span class="step-params">{{ stepText(step) }}</span>
                </div>
                <span v-if="step.critical" class="step-critical">关键</span>
              </li>
            </ol>
          </Transition>

          <div class="scene-card-foot">
            <div class="foot-left">
              <button class="icon-btn sm" title="编辑场景" @click="openEdit(scene)">
                <Pencil :size="12" />
              </button>
              <button class="icon-btn sm" title="复制场景" @click="duplicate(scene)">
                <Copy :size="12" />
              </button>
              <button class="icon-btn sm danger" title="删除场景" @click="remove(scene)">
                <Trash2 :size="12" />
              </button>
            </div>
            <button
              class="btn btn-sm btn-primary run-btn"
              :disabled="Boolean(runningId)"
              @click="runScene(scene)"
            >
              <Play :size="12" />
              {{ runningId === scene.id ? '执行中…' : '执行场景' }}
            </button>
          </div>
        </article>

        <button class="scene-card add-card" @click="openCreate">
          <div class="add-icon"><Plus :size="20" /></div>
          <div class="add-title">新建场景</div>
          <div class="add-desc">选择设备、设置参数与条件，组合一段自动化</div>
        </button>
      </div>

      <div v-else class="panel empty-scenes">
        <div class="empty-icon"><Workflow :size="20" /></div>
        <div class="empty-title">还没有自定义场景</div>
        <p class="empty-desc">
          创建一个「阅读模式」：书房台灯调到 80% 暖白光，客厅空调设为 25°C，
          关键动作失败时自动把台灯调到全亮。
        </p>
        <button class="btn btn-sm btn-primary" @click="openCreate">
          <Plus :size="12" /> 创建第一个场景
        </button>
      </div>
    </section>

    <SceneEditor
      :open="editorOpen"
      :scene="editingScene"
      @close="editorOpen = false"
      @save="handleSave"
    />
  </div>
</template>

<style scoped>
.scenes-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.flow-strip {
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.flow-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.flow-title {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
}

.flow-track {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
  padding: 7px 0 2px;
  position: relative;
}

.flow-node-wrap {
  display: flex;
  align-items: center;
  gap: 5px;
}

.flow-node {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid rgba(180, 74, 38, 0.13);
  background: rgba(180, 74, 38, 0.045);
  color: var(--text-2);
  font-size: 10px;
  white-space: nowrap;
}

.flow-node svg {
  color: var(--mint);
}

.flow-node.fallback {
  border-color: rgba(169, 105, 28, 0.14);
  background: rgba(169, 105, 28, 0.04);
}

.flow-node.fallback svg {
  color: var(--warning);
}

.flow-arrow {
  color: var(--text-4);
  font-size: 10px;
}

.flow-loop {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-left: auto;
  font-size: 8.5px;
  color: var(--text-4);
}

.loop-line {
  width: 22px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--line-strong));
}

.flow-stats {
  display: flex;
  gap: 26px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.flow-stats > div {
  display: flex;
  align-items: baseline;
  gap: 5px;
}

.flow-stats strong {
  font-size: 18px;
  font-weight: 550;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.flow-stats span {
  font-size: 9px;
  color: var(--text-4);
}

.scene-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12.5px;
  font-weight: 550;
  color: var(--text-2);
}

.section-title svg {
  color: var(--text-3);
}

.section-count {
  font-size: 8.5px;
  color: var(--text-4);
  background: rgba(41, 37, 36, 0.04);
  border-radius: 4px;
  min-width: 16px;
  height: 16px;
  display: inline-grid;
  place-items: center;
  font-variant-numeric: tabular-nums;
}

.section-note {
  font-size: 9px;
  color: var(--text-4);
}

.scene-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(302px, 1fr));
  gap: 12px;
}

.scene-card {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 11px;
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.scene-card:hover {
  border-color: var(--line-strong);
}

.scene-card.running {
  border-color: rgba(180, 74, 38, 0.2);
  box-shadow: 0 0 30px rgba(180, 74, 38, 0.06);
}

.scene-card.custom {
  background:
    radial-gradient(circle at 100% 0%, rgba(95, 107, 82, 0.05), transparent 50%),
    linear-gradient(180deg, rgba(255, 253, 249, 0.72), rgba(248, 243, 235, 0.8));
}

.scene-card-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.scene-glyph {
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  color: var(--mint);
  background: var(--mint-soft);
  border: 1px solid rgba(180, 74, 38, 0.14);
}

.scene-glyph.custom {
  color: var(--indigo);
  background: var(--indigo-soft);
  border-color: rgba(95, 107, 82, 0.14);
}

.scene-title-copy {
  flex: 1;
  min-width: 0;
}

.scene-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 550;
  color: var(--text);
  letter-spacing: -0.01em;
}

.custom-badge {
  font-size: 7.5px;
  font-weight: 400;
  color: var(--indigo);
  background: var(--indigo-soft);
  padding: 1px 4px;
  border-radius: 3px;
}

.scene-desc {
  font-size: 9.5px;
  line-height: 1.55;
  color: var(--text-4);
  margin-top: 3px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 29px;
}

.scene-step-badge {
  flex: 0 0 auto;
  font-size: 8.5px;
  color: var(--text-3);
  border: 1px solid var(--line);
  padding: 2px 6px;
  border-radius: 5px;
  font-variant-numeric: tabular-nums;
}

.scene-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.steps-toggle {
  display: flex;
  align-items: center;
  gap: 3px;
  align-self: flex-start;
  border: none;
  background: transparent;
  color: var(--text-4);
  font-size: 9px;
  padding: 0;
}

.steps-toggle:hover {
  color: var(--text-2);
}

.steps-toggle svg {
  transition: transform 0.2s ease;
}

.steps-toggle svg.flipped {
  transform: rotate(180deg);
}

.step-preview {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 9px;
  border-radius: 9px;
  border: 1px solid var(--line);
  background: rgba(41, 37, 36, 0.05);
  max-height: 150px;
  overflow-y: auto;
}

.step-preview li {
  display: flex;
  align-items: flex-start;
  gap: 7px;
}

.step-index {
  flex: 0 0 14px;
  height: 14px;
  border-radius: 4px;
  display: grid;
  place-items: center;
  font-family: var(--font-mono);
  font-size: 7.5px;
  color: var(--text-4);
  background: rgba(41, 37, 36, 0.04);
  margin-top: 1px;
}

.step-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.step-device {
  font-size: 9px;
  color: var(--text-2);
}

.step-params {
  font-size: 8px;
  color: var(--text-4);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-critical {
  font-size: 7px;
  color: var(--amber);
  border: 1px solid rgba(192, 138, 62, 0.15);
  padding: 0 3px;
  border-radius: 3px;
  white-space: nowrap;
}

.scene-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px solid var(--line);
}

.foot-left {
  display: flex;
  gap: 4px;
}

.run-btn {
  min-width: 96px;
}

.run-btn.btn-primary {
  background: transparent;
  color: var(--mint);
  border-color: var(--mint-line);
  font-weight: 500;
}

.run-btn.btn-primary:hover {
  background: var(--mint);
  color: #fff9f4;
  border-color: var(--mint);
}

.icon-btn.danger:hover {
  color: var(--critical);
  background: var(--critical-soft);
  border-color: rgba(168, 58, 50, 0.2);
}

.scene-skeleton {
  height: 210px;
  border-radius: var(--radius-lg);
}

.add-card {
  align-items: center;
  justify-content: center;
  text-align: center;
  min-height: 210px;
  border: 1px dashed rgba(41, 37, 36, 0.16);
  background: rgba(41, 37, 36, 0.012);
  color: var(--text-3);
  gap: 6px;
}

.add-card:hover {
  border-color: rgba(180, 74, 38, 0.2);
  background: rgba(180, 74, 38, 0.025);
  transform: translateY(-2px);
}

.add-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  background: rgba(41, 37, 36, 0.03);
  margin-bottom: 2px;
}

.add-title {
  font-size: 12px;
  color: var(--text-2);
}

.add-desc {
  font-size: 9.5px;
  color: var(--text-4);
  max-width: 190px;
  line-height: 1.55;
}

.empty-scenes {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 7px;
  padding: 34px 20px;
}

.empty-title {
  font-size: 13px;
  color: var(--text-2);
}

.empty-desc {
  font-size: 10px;
  color: var(--text-4);
  max-width: 430px;
  line-height: 1.65;
  margin-bottom: 5px;
}

@media (max-width: 760px) {
  .scene-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .flow-track {
    gap: 4px;
  }

  .flow-node {
    height: 27px;
    padding: 0 7px;
    font-size: 9px;
  }

  .flow-node svg {
    display: none;
  }

  .flow-loop,
  .section-note {
    display: none;
  }

  .flow-stats {
    justify-content: space-between;
    gap: 8px;
  }

  .flow-stats strong {
    font-size: 15px;
  }
}
</style>
