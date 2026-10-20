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

const glowColor = computed(() => {
  if (!props.device.online) return 'rgba(148,178,209,.12)'
  if (!isActive.value) return 'rgba(148,178,209,.14)'
  const p = props.device.properties
  switch (props.device.type) {
    case 'light':
      return `${p.color_hex || '#f8c66a'}77`
    case 'ac':
      return 'rgba(139,149,248,.5)'
    case 'purifier':
      return 'rgba(94,234,212,.42)'
    case 'humidifier':
      return 'rgba(125,211,252,.42)'
    case 'socket':
      return 'rgba(248,198,106,.35)'
    case 'speaker':
      return 'rgba(139,149,248,.42)'
    case 'vacuum':
      return 'rgba(94,234,212,.35)'
    default:
      return 'rgba(94,234,212,.3)'
  }
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
  return props.device.properties.color_hex || '#f8c66a'
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
      <div
        class="device-icon"
        :style="{ color: iconTint, boxShadow: `0 0 24px ${glowColor}`, borderColor: glowColor }"
      >
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
  gap: 12px;
  padding: 16px;
  min-height: 164px;
  border-radius: 17px;
  border: 1px solid var(--line);
  background:
    radial-gradient(circle at 100% 0%, rgba(94, 234, 212, 0.035), transparent 50%),
    linear-gradient(180deg, rgba(20, 32, 46, 0.56), rgba(10, 17, 26, 0.66));
  cursor: pointer;
  outline: none;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.device-card:hover,
.device-card:focus-visible {
  transform: translateY(-3px);
  border-color: rgba(148, 178, 209, 0.22);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.24);
}

.device-card.active {
  border-color: rgba(94, 234, 212, 0.17);
  background:
    radial-gradient(circle at 100% 0%, rgba(94, 234, 212, 0.08), transparent 55%),
    linear-gradient(180deg, rgba(20, 36, 49, 0.62), rgba(10, 17, 26, 0.7));
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
  border-radius: 12px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
  transition: color 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.card-status {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
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
  box-shadow: 0 0 7px rgba(94, 234, 212, 0.8);
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
  font-size: 13.5px;
  font-weight: 550;
  letter-spacing: -0.01em;
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
  box-shadow: 0 0 8px currentColor;
}

.card-room {
  font-size: 10.5px;
  color: var(--text-3);
  margin-top: 2px;
}

.card-metric {
  font-size: 11.5px;
  color: var(--text-2);
  letter-spacing: 0.01em;
  font-variant-numeric: tabular-nums;
  padding: 7px 9px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(148, 178, 209, 0.06);
  min-height: 31px;
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
  font-size: 8.5px;
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
