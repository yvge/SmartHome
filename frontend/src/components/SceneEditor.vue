<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import {
  ChevronDown,
  GripVertical,
  Plus,
  Save,
  ShieldAlert,
  Trash2,
  Workflow,
  X,
} from 'lucide-vue-next'
import DeviceIcon from '@/components/DeviceIcon.vue'
import { useHomeStore } from '@/stores/home'
import { useUiStore } from '@/stores/ui'
import type { Capability, Device, Scene, SceneCondition, SceneStep } from '@/types'

const props = defineProps<{
  scene?: Scene | null
  open: boolean
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'save', payload: Record<string, unknown>): void
}>()

const home = useHomeStore()
const ui = useUiStore()

const ICONS = [
  'home', 'moon', 'sunrise', 'clapperboard', 'leaf', 'sparkles',
  'door-open', 'book-open', 'coffee', 'briefcase', 'film', 'zap',
]

interface EditableStep {
  key: string
  device_id: string
  params: Record<string, any>
  critical: boolean
  delay_ms: number
}

interface FormState {
  name: string
  icon: string
  description: string
  conditionEnabled: boolean
  conditionType: 'time' | 'temperature' | 'humidity'
  timeStart: string
  timeEnd: string
  conditionOp: string
  conditionValue: number
  conditionOptional: boolean
  steps: EditableStep[]
  fallback: EditableStep[]
}

let stepSeed = 0
const form = reactive<FormState>(createEmptyForm())
const advancedOpen = ref(false)
const fallbackOpen = ref(false)
const saving = ref(false)

function newStep(deviceId = ''): EditableStep {
  stepSeed += 1
  return {
    key: `step_${Date.now()}_${stepSeed}`,
    device_id: deviceId,
    params: {},
    critical: false,
    delay_ms: 220,
  }
}

function createEmptyForm(): FormState {
  return {
    name: '',
    icon: 'sparkles',
    description: '',
    conditionEnabled: false,
    conditionType: 'time',
    timeStart: '18:00',
    timeEnd: '23:00',
    conditionOp: '>=',
    conditionValue: 26,
    conditionOptional: true,
    steps: [newStep()],
    fallback: [],
  }
}

const controllableDevices = computed(() =>
  home.devices.filter((device) => device.online && device.type !== 'sensor'),
)

function deviceById(id: string): Device | undefined {
  return home.devices.find((device) => device.id === id)
}

function writableCapabilities(deviceId: string): Capability[] {
  const device = deviceById(deviceId)
  if (!device) return []
  return device.capabilities.filter((capability) => capability.type !== 'readonly')
}

function defaultParams(device: Device): Record<string, any> {
  const params: Record<string, any> = {}
  for (const capability of device.capabilities) {
    if (capability.type === 'readonly') continue
    if (capability.type === 'boolean') {
      params[capability.key] = capability.key === 'power' ? true : Boolean(capability.default)
    } else if (capability.type === 'range') {
      const current = Number(device.properties[capability.key])
      params[capability.key] = Number.isFinite(current) ? current : Number(capability.default ?? 0)
    } else if (capability.type === 'enum') {
      params[capability.key] = device.properties[capability.key] || capability.default || capability.options?.[0]?.value
    }
  }
  return params
}

function onDeviceChange(step: EditableStep, deviceId: string) {
  step.device_id = deviceId
  const device = deviceById(deviceId)
  step.params = device ? defaultParams(device) : {}
}

function addStep() {
  form.steps.push(newStep())
}

function addFallback() {
  form.fallback.push(newStep())
}

function removeStep(index: number) {
  if (form.steps.length <= 1) {
    ui.warning('至少保留一个动作')
    return
  }
  form.steps.splice(index, 1)
}

function removeFallback(index: number) {
  form.fallback.splice(index, 1)
}

function moveStep(index: number, offset: number) {
  const target = index + offset
  if (target < 0 || target >= form.steps.length) return
  const [item] = form.steps.splice(index, 1)
  form.steps.splice(target, 0, item)
}

function fillFromScene(scene: Scene) {
  const condition = scene.condition
  Object.assign(form, {
    name: scene.name.replace(/ 副本$/, ''),
    icon: scene.icon || 'sparkles',
    description: scene.description || '',
    conditionEnabled: Boolean(condition) && !condition?.optional,
    conditionType: (condition?.type as FormState['conditionType']) || 'time',
    timeStart: condition?.type === 'time' ? String(condition.value?.[0] || '18:00') : '18:00',
    timeEnd: condition?.type === 'time' ? String(condition.value?.[1] || '23:00') : '23:00',
    conditionOp: condition?.op || '>=',
    conditionValue: condition?.type === 'time' ? 26 : Number(condition?.value ?? 26),
    conditionOptional: Boolean(condition?.optional),
    steps: scene.steps.map((step) => ({
      key: `step_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      device_id: step.device_id,
      params: { ...step.params },
      critical: Boolean(step.critical),
      delay_ms: Number(step.delay_ms ?? 220),
    })),
    fallback: scene.fallback.map((step) => ({
      key: `step_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      device_id: step.device_id,
      params: { ...step.params },
      critical: Boolean(step.critical),
      delay_ms: Number(step.delay_ms ?? 220),
    })),
  })
  if (form.fallback.length) fallbackOpen.value = true
}

watch(
  () => [props.open, props.scene?.id],
  () => {
    if (!props.open) return
    if (props.scene) {
      fillFromScene(props.scene)
      advancedOpen.value = true
    } else {
      stepSeed = 0
      Object.assign(form, createEmptyForm())
      advancedOpen.value = false
      fallbackOpen.value = false
    }
    if (!form.steps.length) form.steps = [newStep()]
  },
  { immediate: true },
)

function buildCondition(): SceneCondition | null {
  if (!form.conditionEnabled) return null
  if (form.conditionType === 'time') {
    return {
      type: 'time',
      value: [form.timeStart, form.timeEnd],
      optional: form.conditionOptional,
      label: '时间条件',
    }
  }
  return {
    type: form.conditionType,
    op: form.conditionOp,
    value: form.conditionValue,
    optional: form.conditionOptional,
    label: form.conditionType === 'temperature' ? '温度条件' : '湿度条件',
  }
}

function serializeStep(step: EditableStep): SceneStep | null {
  if (!step.device_id) return null
  const device = deviceById(step.device_id)
  if (!device) return null
  return {
    device_id: step.device_id,
    params: { ...step.params },
    critical: step.critical,
    delay_ms: step.delay_ms,
  }
}

function validate(): string | null {
  if (!form.name.trim()) return '请填写场景名称'
  if (!form.steps.some((step) => step.device_id)) return '至少选择一个设备动作'
  for (const step of form.steps) {
    if (!step.device_id) continue
    if (!Object.keys(step.params).length) return `${deviceById(step.device_id)?.name || '设备'}缺少动作参数`
  }
  return null
}

function submit() {
  const error = validate()
  if (error) {
    ui.warning(error)
    return
  }
  const steps = form.steps.map(serializeStep).filter(Boolean) as SceneStep[]
  const fallback = form.fallback.map(serializeStep).filter(Boolean) as SceneStep[]
  saving.value = true
  emit('save', {
    name: form.name.trim(),
    icon: form.icon,
    description: form.description.trim(),
    condition: buildCondition(),
    steps,
    fallback,
  })
  window.setTimeout(() => (saving.value = false), 400)
}

function close() {
  emit('close')
}

function setConditionType(value: string) {
  form.conditionType = value as FormState['conditionType']
}

function updateRange(step: EditableStep, capability: Capability, event: Event) {
  const value = Number((event.target as HTMLInputElement).value)
  step.params[capability.key] = value
}

function updateBoolean(step: EditableStep, capability: Capability, event: Event) {
  step.params[capability.key] = (event.target as HTMLInputElement).checked
}

function updateEnum(step: EditableStep, capability: Capability, event: Event) {
  step.params[capability.key] = (event.target as HTMLSelectElement).value
}

function stepSummary(step: EditableStep): string {
  const device = deviceById(step.device_id)
  if (!device) return '未选择设备'
  const parts = Object.entries(step.params).map(([key, value]) => {
    const capability = device.capabilities.find((item) => item.key === key)
    if (capability?.type === 'boolean') return `${capability.label}${value ? '开' : '关'}`
    if (capability?.type === 'enum') {
      const option = capability.options?.find((item) => item.value === value)
      return option?.label || String(value)
    }
    return `${capability?.label || key} ${value}${capability?.unit || ''}`
  })
  return parts.length ? parts.join(' · ') : '待设置参数'
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="editor-backdrop" @click.self="close">
        <div class="editor-panel" role="dialog" aria-modal="true" aria-label="场景编排器">
          <header class="editor-head">
            <div class="editor-title-wrap">
              <div class="editor-icon"><Workflow :size="18" /></div>
              <div>
                <div class="panel-kicker">场景编辑</div>
                <h3 class="editor-title">{{ scene ? '编辑场景' : '新建场景' }}</h3>
                <p class="editor-sub">把几个设备动作排好顺序，保存成可以一键执行的场景</p>
              </div>
            </div>
            <button class="icon-btn sm" aria-label="关闭" @click="close">
              <X :size="15" />
            </button>
          </header>

          <div class="editor-scroll">
            <section class="editor-section">
              <div class="section-label">基础信息</div>
              <div class="field-row">
                <label class="field">
                  <span class="field-label">场景名称</span>
                  <input v-model="form.name" class="input" maxlength="20" placeholder="例如：阅读模式" />
                </label>
                <label class="field icon-field">
                  <span class="field-label">图标</span>
                  <select v-model="form.icon" class="select">
                    <option v-for="icon in ICONS" :key="icon" :value="icon">{{ icon }}</option>
                  </select>
                </label>
              </div>
              <label class="field">
                <span class="field-label">场景描述</span>
                <input
                  v-model="form.description"
                  class="input"
                  maxlength="80"
                  placeholder="一句话描述这个场景带来的体验"
                />
              </label>
            </section>

            <section class="editor-section">
              <div class="section-head-row">
                <div class="section-label">执行条件</div>
                <button
                  class="toggle"
                  :class="{ on: form.conditionEnabled }"
                  role="switch"
                  :aria-checked="form.conditionEnabled"
                  aria-label="启用执行条件"
                  @click="form.conditionEnabled = !form.conditionEnabled"
                ></button>
              </div>
              <div v-if="form.conditionEnabled" class="condition-box">
                <div class="segmented">
                  <button
                    v-for="option in [
                      { value: 'time', label: '时间' },
                      { value: 'temperature', label: '温度' },
                      { value: 'humidity', label: '湿度' },
                    ]"
                    :key="option.value"
                    :class="{ active: form.conditionType === option.value }"
                    @click="setConditionType(option.value)"
                  >
                    {{ option.label }}
                  </button>
                </div>

                <div v-if="form.conditionType === 'time'" class="time-row">
                  <input v-model="form.timeStart" class="input time-input" type="time" aria-label="开始时间" />
                  <span class="time-sep">至</span>
                  <input v-model="form.timeEnd" class="input time-input" type="time" aria-label="结束时间" />
                </div>

                <div v-else class="threshold-row">
                  <select v-model="form.conditionOp" class="select op-select" aria-label="比较方式">
                    <option value=">=">不低于</option>
                    <option value=">">大于</option>
                    <option value="<=">不高于</option>
                    <option value="<">小于</option>
                  </select>
                  <div class="threshold-input">
                    <input v-model.number="form.conditionValue" class="input" type="number" aria-label="阈值" />
                    <span>{{ form.conditionType === 'temperature' ? '°C' : '%' }}</span>
                  </div>
                </div>

                <label class="check-row">
                  <input v-model="form.conditionOptional" type="checkbox" />
                  <span>条件不满足时仍继续执行（可选条件）</span>
                </label>
              </div>
              <div v-else class="condition-off">未设置条件，触发后立即执行全部动作</div>
            </section>

            <section class="editor-section">
              <div class="section-head-row">
                <div>
                  <div class="section-label">设备动作序列</div>
                  <div class="section-hint">按顺序依次执行，可设置关键动作与延时</div>
                </div>
                <button class="btn btn-xs" @click="addStep"><Plus :size="11" /> 添加动作</button>
              </div>

              <div class="steps">
                <div v-for="(step, index) in form.steps" :key="step.key" class="step-card">
                  <div class="step-order">
                    <GripVertical :size="12" />
                    <span>{{ index + 1 }}</span>
                    <button class="order-btn" :disabled="index === 0" @click="moveStep(index, -1)">↑</button>
                    <button class="order-btn" :disabled="index === form.steps.length - 1" @click="moveStep(index, 1)">↓</button>
                  </div>

                  <div class="step-body">
                    <div class="step-row">
                      <div class="device-select">
                        <DeviceIcon
                          v-if="deviceById(step.device_id)"
                          :icon="deviceById(step.device_id)!.icon"
                          :size="14"
                        />
                        <select
                          :value="step.device_id"
                          class="select"
                          aria-label="选择设备"
                          @change="onDeviceChange(step, ($event.target as HTMLSelectElement).value)"
                        >
                          <option value="">选择设备</option>
                          <option v-for="device in controllableDevices" :key="device.id" :value="device.id">
                            {{ device.room }} · {{ device.name }}
                          </option>
                        </select>
                      </div>
                      <button class="icon-btn sm danger" title="删除动作" @click="removeStep(index)">
                        <Trash2 :size="12" />
                      </button>
                    </div>

                    <div v-if="step.device_id" class="param-grid">
                      <div
                        v-for="capability in writableCapabilities(step.device_id)"
                        :key="capability.key"
                        class="param"
                      >
                        <template v-if="capability.type === 'boolean'">
                          <label class="param-bool">
                            <span>{{ capability.label }}</span>
                            <input
                              type="checkbox"
                              :checked="Boolean(step.params[capability.key])"
                              @change="updateBoolean(step, capability, $event)"
                            />
                          </label>
                        </template>
                        <template v-else-if="capability.type === 'range'">
                          <div class="param-head">
                            <span>{{ capability.label }}</span>
                            <em>{{ step.params[capability.key] }}{{ capability.unit }}</em>
                          </div>
                          <input
                            class="slider"
                            type="range"
                            :min="capability.min ?? 0"
                            :max="capability.max ?? 100"
                            :step="capability.step ?? 1"
                            :value="Number(step.params[capability.key])"
                            :style="{
                              '--fill': `${((Number(step.params[capability.key]) - (capability.min ?? 0)) / Math.max(1, (capability.max ?? 100) - (capability.min ?? 0))) * 100}%`,
                            }"
                            :aria-label="capability.label"
                            @input="updateRange(step, capability, $event)"
                          />
                        </template>
                        <template v-else-if="capability.type === 'enum'">
                          <div class="param-head"><span>{{ capability.label }}</span></div>
                          <select
                            class="select compact"
                            :value="step.params[capability.key]"
                            :aria-label="capability.label"
                            @change="updateEnum(step, capability, $event)"
                          >
                            <option v-for="option in capability.options || []" :key="option.value" :value="option.value">
                              {{ option.label }}
                            </option>
                          </select>
                        </template>
                      </div>
                    </div>

                    <div v-if="step.device_id" class="step-meta-row">
                      <label class="check-row small">
                        <input v-model="step.critical" type="checkbox" />
                        <span>关键动作（失败触发兜底）</span>
                      </label>
                      <label class="delay-field">
                        <span>延时</span>
                        <input v-model.number="step.delay_ms" class="input tiny" type="number" min="0" max="2000" step="50" />
                        <span>ms</span>
                      </label>
                    </div>

                    <div v-if="step.device_id" class="step-summary">{{ stepSummary(step) }}</div>
                  </div>
                </div>
              </div>
            </section>

            <section class="editor-section">
              <button class="collapse-head" @click="advancedOpen = !advancedOpen">
                <span class="section-label">高级：异常兜底动作</span>
                <ChevronDown :size="14" :class="{ flipped: advancedOpen }" />
              </button>
              <div v-if="advancedOpen" class="collapse-body">
                <div class="section-hint">
                  当关键动作执行失败时，依次执行以下兜底动作，尽最大可能恢复家庭状态。
                </div>
                <div v-for="(step, index) in form.fallback" :key="step.key" class="step-card fallback-step">
                  <div class="step-order fallback-order"><ShieldAlert :size="12" /><span>{{ index + 1 }}</span></div>
                  <div class="step-body">
                    <div class="step-row">
                      <div class="device-select">
                        <select
                          :value="step.device_id"
                          class="select"
                          aria-label="选择兜底设备"
                          @change="onDeviceChange(step, ($event.target as HTMLSelectElement).value)"
                        >
                          <option value="">选择设备</option>
                          <option v-for="device in controllableDevices" :key="device.id" :value="device.id">
                            {{ device.room }} · {{ device.name }}
                          </option>
                        </select>
                      </div>
                      <button class="icon-btn sm danger" title="删除兜底动作" @click="removeFallback(index)">
                        <Trash2 :size="12" />
                      </button>
                    </div>
                    <div v-if="step.device_id" class="param-grid">
                      <div v-for="capability in writableCapabilities(step.device_id)" :key="capability.key" class="param">
                        <template v-if="capability.type === 'boolean'">
                          <label class="param-bool">
                            <span>{{ capability.label }}</span>
                            <input
                              type="checkbox"
                              :checked="Boolean(step.params[capability.key])"
                              @change="updateBoolean(step, capability, $event)"
                            />
                          </label>
                        </template>
                        <template v-else-if="capability.type === 'range'">
                          <div class="param-head">
                            <span>{{ capability.label }}</span>
                            <em>{{ step.params[capability.key] }}{{ capability.unit }}</em>
                          </div>
                          <input
                            class="slider"
                            type="range"
                            :min="capability.min ?? 0"
                            :max="capability.max ?? 100"
                            :step="capability.step ?? 1"
                            :value="Number(step.params[capability.key])"
                            :aria-label="capability.label"
                            @input="updateRange(step, capability, $event)"
                          />
                        </template>
                        <template v-else-if="capability.type === 'enum'">
                          <div class="param-head"><span>{{ capability.label }}</span></div>
                          <select
                            class="select compact"
                            :value="step.params[capability.key]"
                            :aria-label="capability.label"
                            @change="updateEnum(step, capability, $event)"
                          >
                            <option v-for="option in capability.options || []" :key="option.value" :value="option.value">
                              {{ option.label }}
                            </option>
                          </select>
                        </template>
                      </div>
                    </div>
                  </div>
                </div>
                <button class="btn btn-xs add-fallback" @click="addFallback">
                  <Plus :size="11" /> 添加兜底动作
                </button>
              </div>
            </section>
          </div>

          <footer class="editor-foot">
            <span class="editor-tip">
              <ShieldAlert :size="12" />
              执行过程会实时展示在场景运行浮层与运行轨迹页
            </span>
            <div class="editor-actions">
              <button class="btn btn-sm" @click="close">取消</button>
              <button class="btn btn-sm btn-primary" :disabled="saving" @click="submit">
                <Save :size="12" />
                {{ scene ? '保存修改' : '创建场景' }}
              </button>
            </div>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.editor-backdrop {
  position: fixed;
  inset: 0;
  z-index: 340;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(33, 29, 25, 0.34);
  backdrop-filter: blur(8px);
}

.editor-panel {
  width: min(720px, 100%);
  max-height: min(88vh, 900px);
  display: flex;
  flex-direction: column;
  border-radius: 20px;
  border: 1px solid var(--line-strong);
  background: #f7f2ea;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.editor-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 19px 20px 14px;
  border-bottom: 1px solid var(--line);
}

.editor-title-wrap {
  display: flex;
  align-items: flex-start;
  gap: 11px;
}

.editor-icon {
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  color: var(--mint);
  background: var(--mint-soft);
  border: 1px solid rgba(180, 74, 38, 0.16);
}

.editor-title {
  font-size: 18px;
}

.editor-sub {
  font-size: 10px;
  color: var(--text-4);
  margin-top: 1px;
}

.editor-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.editor-section {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.section-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-3);
}

.section-hint {
  font-size: 9.5px;
  color: var(--text-4);
  line-height: 1.5;
}

.section-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.field-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 130px;
  gap: 9px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.icon-field .select {
  height: 38px;
}

.condition-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 11px;
  border: 1px solid var(--line);
  background: rgba(41, 37, 36, 0.018);
}

.condition-off {
  font-size: 10px;
  color: var(--text-4);
  padding: 9px 11px;
  border-radius: 9px;
  border: 1px dashed var(--line);
}

.time-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.time-input {
  width: 130px;
  color-scheme: dark;
}

.time-sep {
  font-size: 10px;
  color: var(--text-4);
}

.threshold-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.op-select {
  width: 106px;
}

.threshold-input {
  position: relative;
  width: 120px;
}

.threshold-input span {
  position: absolute;
  right: 11px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 9px;
  color: var(--text-4);
}

.check-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: var(--text-3);
  cursor: pointer;
}

.check-row input {
  accent-color: var(--mint);
  width: 12px;
  height: 12px;
}

.check-row.small {
  font-size: 9px;
}

.steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-card {
  display: flex;
  gap: 10px;
  padding: 11px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: rgba(41, 37, 36, 0.02);
}

.step-order {
  flex: 0 0 22px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  color: var(--text-4);
  font-size: 9px;
}

.step-order > span {
  width: 18px;
  height: 18px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  background: rgba(180, 74, 38, 0.06);
  color: var(--mint);
  font-family: var(--font-mono);
  font-size: 8px;
}

.order-btn {
  border: none;
  background: transparent;
  color: var(--text-4);
  font-size: 9px;
  padding: 0;
  line-height: 1;
}

.order-btn:hover:not(:disabled) {
  color: var(--text-2);
}

.order-btn:disabled {
  opacity: 0.3;
}

.step-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-row {
  display: flex;
  align-items: center;
  gap: 7px;
}

.device-select {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  color: var(--text-3);
}

.device-select .select {
  height: 32px;
  font-size: 11px;
  padding: 0 28px 0 9px;
}

.param-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
}

.param {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.param-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 9.5px;
  color: var(--text-3);
}

.param-head em {
  font-style: normal;
  font-size: 9px;
  color: var(--text-2);
  font-variant-numeric: tabular-nums;
}

.param-bool {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  height: 30px;
  padding: 0 8px;
  border-radius: 8px;
  border: 1px solid var(--line);
  font-size: 9.5px;
  color: var(--text-3);
}

.param-bool input {
  accent-color: var(--mint);
  width: 13px;
  height: 13px;
}

.select.compact {
  height: 30px;
  font-size: 10px;
  padding: 0 26px 0 8px;
  border-radius: 8px;
}

.slider {
  height: 3px;
}

.step-meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.delay-field {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 9px;
  color: var(--text-4);
}

.input.tiny {
  width: 58px;
  height: 26px;
  padding: 0 6px;
  font-size: 9.5px;
  border-radius: 6px;
}

.step-summary {
  font-size: 9px;
  color: var(--text-4);
  padding: 5px 7px;
  border-radius: 6px;
  background: rgba(180, 74, 38, 0.03);
  border: 1px solid rgba(180, 74, 38, 0.06);
  line-height: 1.5;
}

.icon-btn.danger:hover {
  color: var(--critical);
  background: var(--critical-soft);
  border-color: rgba(168, 58, 50, 0.2);
}

.collapse-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 8px 0;
  border: none;
  background: transparent;
  color: var(--text-3);
}

.collapse-head svg {
  transition: transform 0.2s ease;
}

.collapse-head svg.flipped {
  transform: rotate(180deg);
}

.collapse-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fallback-step {
  border-color: rgba(169, 105, 28, 0.11);
  background: rgba(169, 105, 28, 0.02);
}

.fallback-order {
  color: var(--warning);
}

.fallback-order > span {
  background: rgba(169, 105, 28, 0.08);
  color: var(--warning);
}

.add-fallback {
  align-self: flex-start;
}

.editor-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 13px 20px;
  border-top: 1px solid var(--line);
  background: rgba(244, 240, 233, 0.9);
  flex-wrap: wrap;
}

.editor-tip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 9px;
  color: var(--text-4);
}

.editor-actions {
  display: flex;
  gap: 7px;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active .editor-panel,
.modal-leave-active .editor-panel {
  transition: transform 0.24s cubic-bezier(0.2, 0.8, 0.3, 1), opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .editor-panel,
.modal-leave-to .editor-panel {
  transform: translateY(14px) scale(0.985);
  opacity: 0;
}

@media (max-width: 760px) {
  .editor-backdrop {
    padding: 0;
  }

  .editor-panel {
    width: 100%;
    height: 100dvh;
    max-height: 100dvh;
    border-radius: 0;
    border: none;
  }

  .field-row {
    grid-template-columns: minmax(0, 1fr);
  }

  .param-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .editor-tip {
    display: none;
  }

  .editor-actions {
    width: 100%;
  }

  .editor-actions .btn {
    flex: 1;
  }
}
</style>
