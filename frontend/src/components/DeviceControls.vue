<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import type { Capability, Device } from '@/types'

const props = defineProps<{ device: Device }>()
const emit = defineEmits<{ (event: 'change', patch: Record<string, any>): void }>()

const writable = computed(() =>
  props.device.capabilities.filter((capability) => capability.type !== 'readonly'),
)
const readonly = computed(() =>
  props.device.capabilities.filter((capability) => capability.type === 'readonly'),
)

const values = reactive<Record<string, number>>({})

function syncValues(device: Device) {
  for (const capability of device.capabilities) {
    if (capability.type !== 'range') continue
    const raw = Number(device.properties[capability.key])
    values[capability.key] = Number.isFinite(raw)
      ? raw
      : Number(capability.default ?? capability.min ?? 0)
  }
}

watch(() => props.device, (device) => syncValues(device), { immediate: true, deep: true })

function booleanValue(key: string): boolean {
  return Boolean(props.device.properties[key])
}

function toggleBoolean(key: string) {
  if (!props.device.online) return
  emit('change', { [key]: !booleanValue(key) })
}

function setEnum(key: string, value: string) {
  if (!props.device.online) return
  emit('change', { [key]: value })
}

function commitRange(capability: Capability) {
  if (!props.device.online) return
  emit('change', { [capability.key]: Number(values[capability.key]) })
}

function fillPercent(capability: Capability): string {
  const min = capability.min ?? 0
  const max = capability.max ?? 100
  const value = Number(values[capability.key] ?? min)
  const ratio = max === min ? 0 : ((value - min) / (max - min)) * 100
  return `${Math.min(100, Math.max(0, ratio))}%`
}

function readonlyValue(capability: Capability): string {
  const raw = props.device.properties[capability.key]
  if (raw === undefined || raw === null) return '--'
  if (typeof raw === 'number' && !Number.isInteger(raw)) return raw.toFixed(1)
  return String(raw)
}

function isPowerRow(capability: Capability): boolean {
  return capability.type === 'boolean' && capability.key === 'power'
}

function hintFor(capability: Capability): string {
  if (capability.key === 'color_temp') return '暖光 2700K · 中性 4000K · 冷白 6500K'
  if (capability.key === 'playing') return '让音箱开始或暂停播放'
  if (capability.key === 'position') return '0% 完全闭合 · 100% 完全打开'
  if (capability.key === 'target_temp') return '建议 26°C，每上调 1°C 更省电'
  if (isPowerRow(capability)) {
    const type = props.device.type
    if (type === 'vacuum') return '启动或停止清扫'
    if (type === 'socket') return '控制插座通断电'
    return '电源开关'
  }
  return ''
}
</script>

<template>
  <div class="device-controls" :class="{ offline: !device.online }">
    <div v-if="readonly.length" class="telemetry">
      <div v-for="capability in readonly" :key="capability.key" class="telemetry-item">
        <span class="telemetry-label">{{ capability.label }}</span>
        <strong class="telemetry-value">
          {{ readonlyValue(capability) }}<em v-if="capability.unit">{{ capability.unit }}</em>
        </strong>
      </div>
    </div>

    <div v-for="capability in writable" :key="capability.key" class="control-block">
      <template v-if="capability.type === 'boolean'">
        <div class="control-head" :class="{ power: isPowerRow(capability) }">
          <div>
            <div class="control-label">{{ capability.label }}</div>
            <div v-if="hintFor(capability)" class="control-hint">{{ hintFor(capability) }}</div>
          </div>
          <button
            class="toggle"
            :class="{ on: booleanValue(capability.key) }"
            :disabled="!device.online"
            role="switch"
            :aria-checked="booleanValue(capability.key)"
            :aria-label="capability.label"
            @click="toggleBoolean(capability.key)"
          ></button>
        </div>
      </template>

      <template v-else-if="capability.type === 'range'">
        <div class="control-head">
          <div>
            <div class="control-label">{{ capability.label }}</div>
            <div v-if="hintFor(capability)" class="control-hint">{{ hintFor(capability) }}</div>
          </div>
          <span class="control-value">
            {{ values[capability.key] }}<em>{{ capability.unit }}</em>
          </span>
        </div>
        <input
          v-model.number="values[capability.key]"
          class="slider"
          :class="{ warm: capability.key === 'color_temp' }"
          type="range"
          :min="capability.min ?? 0"
          :max="capability.max ?? 100"
          :step="capability.step ?? 1"
          :style="{ '--fill': fillPercent(capability) }"
          :disabled="!device.online"
          :aria-label="capability.label"
          @change="commitRange(capability)"
        />
        <div class="range-scale">
          <span>{{ capability.min }}{{ capability.unit }}</span>
          <span>{{ capability.max }}{{ capability.unit }}</span>
        </div>
      </template>

      <template v-else-if="capability.type === 'enum'">
        <div class="control-head">
          <div class="control-label">{{ capability.label }}</div>
        </div>
        <div class="segmented" role="group" :aria-label="capability.label">
          <button
            v-for="option in capability.options || []"
            :key="option.value"
            :class="{ active: device.properties[capability.key] === option.value }"
            :disabled="!device.online"
            @click="setEnum(capability.key, option.value)"
          >
            {{ option.label }}
          </button>
        </div>
      </template>
    </div>

    <div v-if="!writable.length" class="sensor-note">
      这是只读传感器，数据由环境模拟器实时上报。
    </div>
    <div v-if="!device.online" class="offline-note">
      设备处于离线状态，控制指令将无法下发。可在下方模拟重新上线。
    </div>
  </div>
</template>

<style scoped>
.device-controls {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.device-controls.offline {
  opacity: 0.68;
}

.telemetry {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(92px, 1fr));
  gap: 8px;
  padding: 12px;
  border-radius: 13px;
  border: 1px solid var(--line);
  background: rgba(41, 37, 36, 0.05);
}

.telemetry-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.telemetry-label {
  font-size: 9.5px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-4);
}

.telemetry-value {
  font-size: 15px;
  font-weight: 550;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.telemetry-value em {
  font-style: normal;
  font-size: 9.5px;
  color: var(--text-3);
  margin-left: 2px;
}

.control-block {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.control-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.control-head.power {
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}

.control-label {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--text);
}

.control-hint {
  font-size: 10.5px;
  color: var(--text-4);
  margin-top: 2px;
}

.control-value {
  font-size: 15px;
  font-weight: 550;
  color: var(--text);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.control-value em {
  font-style: normal;
  font-size: 10px;
  color: var(--text-3);
  margin-left: 2px;
}

.range-scale {
  display: flex;
  justify-content: space-between;
  font-size: 9px;
  color: var(--text-4);
  font-variant-numeric: tabular-nums;
  margin-top: -4px;
}

.sensor-note,
.offline-note {
  font-size: 11px;
  line-height: 1.6;
  color: var(--text-3);
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(41, 37, 36, 0.02);
}

.offline-note {
  color: var(--warning);
  border-color: rgba(169, 105, 28, 0.18);
  background: rgba(169, 105, 28, 0.05);
}

.segmented {
  flex-wrap: wrap;
}

.segmented button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
