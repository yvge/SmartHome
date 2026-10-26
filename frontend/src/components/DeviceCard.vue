<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import type { Device } from '@/types'
import { acModeLabel, devicePrimaryMetric, purifierModeLabel } from '@/utils/format'
import DeviceIcon from '@/components/DeviceIcon.vue'

const props = defineProps<{ device: Device }>()
const emit = defineEmits<{
  (event: 'select', device: Device): void
  (event: 'toggle', device: Device, value: boolean): void
}>()

const canToggle = computed(() =>
  ['light', 'ac', 'purifier', 'humidifier', 'socket', 'speaker', 'vacuum'].includes(props.device.type),
)

const isActive = computed(() => {
  const p = props.device.properties
  switch (props.device.type) {
    case 'light':
    case 'ac':
    case 'purifier':
    case 'humidifier':
    case 'socket':
    case 'vacuum':
      return Boolean(p.power)
    case 'speaker':
      return Boolean(p.playing)
    case 'curtain':
      return Number(p.position) > 0
    case 'sensor':
      return true
    default:
      return false
  }
})

const metric = computed(() => devicePrimaryMetric(props.device))

const statusText = computed(() => {
  if (!props.device.online) return '离线'
  if (props.device.type === 'sensor') return '采集中'
  if (props.device.type === 'curtain') return Number(props.device.properties.position) > 0 ? '已打开' : '已闭合'
  if (isActive.value) return '运行中'
  return '待机'
})

const iconTint = computed(() => {
  const p = props.device.properties
  if (!props.device.online) return 'var(--text-4)'
  if (!isActive.value) return 'var(--text-2)'
  if (props.device.type === 'light') return p.color_hex || 'var(--amber)'
  if (props.device.type === 'ac' || props.device.type === 'speaker') return 'var(--indigo)'
  return 'var(--mint)'
})

const colorDot = computed(() => {
  if (props.device.type !== 'light' || !props.device.properties.power) return null
  return props.device.properties.color_hex || '#c08a3e'
})

function toggle() {
  if (!canToggle.value || !props.device.online) return
  emit('toggle', props.device, !Boolean(props.device.properties.power))
}
</script>

<template>
  <article
    class="device-card"
    :class="{ active: isActive, offline: !device.online }"
    role="button"
    tabindex="0"
    :aria-label="`${device.name}，${statusText}，点击查看详情`"
    @click="emit('select', device)"
    @keydown.enter="emit('select', device)"
  >
    <div class="card-top">
      <div class="device-icon" :style="{ color: iconTint }">
        <DeviceIcon :icon="device.icon" :size="20" />
      </div>
      <div class="card-status">
        <span class="status-dot" :class="{ on: device.online && isActive, offline: !device.online }"></span>
        {{ statusText }}
      </div>
      <button
        v-if="canToggle"
        class="toggle"
        :class="{ on: Boolean(device.properties.power) }"
        :disabled="!device.online"
        role="switch"
        :aria-checked="Boolean(device.properties.power)"
        :aria-label="`${device.name}开关`"
        @click.stop="toggle"
      ></button>
    </div>

    <div class="card-body">
      <div class="card-name">
        {{ device.name }}
        <span v-if="colorDot" class="color-dot" :style="{ background: colorDot }"></span>
      </div>
      <div class="card-room">{{ device.room }} · {{ device.type_label }}</div>
    </div>

    <div class="card-metric">{{ metric }}</div>

    <div class="card-foot">
      <span class="device-id mono">{{ device.id }}</span>
      <ChevronRight :size="13" class="chevron" />
    </div>
  </article>
</template>

<style scoped>
.device-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 13px;
  padding: 17px;
  min-height: 168px;
  border-radius: 13px;
  border: 1px solid var(--line);
  background: var(--panel);
  cursor: pointer;
  outline: none;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.device-card::before {
  content: '';
  position: absolute;
  left: 17px;
  right: 17px;
  top: 0;
  height: 2px;
  border-radius: 0 0 2px 2px;
  background: transparent;
  transition: background 0.2s ease;
}

.device-card:hover,
.device-card:focus-visible {
  transform: translateY(-2px);
  border-color: rgba(41, 37, 36, 0.2);
  box-shadow: 0 12px 28px rgba(60, 45, 30, 0.07);
}

.device-card.active {
  border-color: rgba(180, 74, 38, 0.24);
}

.device-card.active::before {
  background: var(--mint);
}

.device-card.offline {
  opacity: 0.62;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 9px;
}

.device-icon {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  background: var(--bg-soft);
  transition: color 0.2s ease, background 0.2s ease, border-color 0.2s ease;
}

.device-card.active .device-icon {
  background: var(--mint-soft);
  border-color: var(--mint-line);
}

.card-status {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--text-3);
  white-space: nowrap;
}

.status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-4);
}

.status-dot.on {
  background: var(--mint);
}

.status-dot.offline {
  background: var(--critical);
}

.card-top .toggle {
  margin-left: auto;
}

.card-body {
  min-width: 0;
}

.card-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-display);
  font-size: 14.5px;
  font-weight: 600;
  letter-spacing: -0.015em;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.color-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex: 0 0 6px;
}

.card-room {
  font-size: 11.5px;
  color: var(--text-3);
  margin-top: 2px;
}

.card-metric {
  font-size: 12px;
  color: var(--text-2);
  letter-spacing: 0.005em;
  font-variant-numeric: tabular-nums;
  padding: 8px 10px;
  border-radius: 7px;
  background: var(--bg);
  border: 1px solid transparent;
  min-height: 32px;
  display: flex;
  align-items: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 2px;
}

.device-id {
  font-size: 9.5px;
  color: var(--text-4);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 80%;
}

.chevron {
  color: var(--text-4);
  opacity: 0;
  transform: translateX(-4px);
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.device-card:hover .chevron {
  opacity: 1;
  transform: translateX(0);
}
</style>
