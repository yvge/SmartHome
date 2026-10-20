<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { HistoryPoint } from '@/types'
import { formatTime } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    points: HistoryPoint[]
    color?: string
    label?: string
    unit?: string
    height?: number
    formatValue?: (value: number) => string
  }>(),
  {
    color: '#5eead4',
    label: '实时功率',
    unit: '',
    height: 78,
  },
)

const container = ref<HTMLElement | null>(null)
const width = ref(320)
const hoverIndex = ref<number | null>(null)
let observer: ResizeObserver | null = null

const gradientId = `spark-${Math.random().toString(36).slice(2, 9)}`
const pad = { top: 8, right: 5, bottom: 8, left: 5 }

onMounted(() => {
  if (!container.value) return
  const measure = () => {
    width.value = Math.max(120, container.value?.clientWidth || 320)
  }
  measure()
  observer = new ResizeObserver(measure)
  observer.observe(container.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
})

const latest = computed<HistoryPoint | null>(() =>
  props.points.length ? props.points[props.points.length - 1] : null,
)

const domain = computed(() => {
  const values = props.points.map((point) => point.value)
  if (!values.length) return { min: 0, max: 1 }
  let min = Math.min(...values)
  let max = Math.max(...values)
  if (min === max) {
    min -= 1
    max += 1
  }
  const span = max - min
  return { min: min - span * 0.22, max: max + span * 0.22 }
})

const plotWidth = computed(() => Math.max(1, width.value - pad.left - pad.right))
const plotHeight = computed(() => Math.max(1, props.height - pad.top - pad.bottom))

const coords = computed(() =>
  props.points.map((point, index) => {
    const x =
      pad.left +
      (props.points.length <= 1 ? 0.5 : index / (props.points.length - 1)) * plotWidth.value
    const ratio = (point.value - domain.value.min) / (domain.value.max - domain.value.min)
    const y = pad.top + (1 - Math.min(1, Math.max(0, ratio))) * plotHeight.value
    return { ...point, x, y }
  }),
)

const linePath = computed(() => {
  if (!coords.value.length) return ''
  return coords.value
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(' ')
})

const areaPath = computed(() => {
  if (!coords.value.length) return ''
  const baseline = props.height - pad.bottom
  const first = coords.value[0]
  const last = coords.value[coords.value.length - 1]
  return `${linePath.value} L${last.x.toFixed(2)},${baseline} L${first.x.toFixed(2)},${baseline} Z`
})

const gridLines = computed(() =>
  [0.25, 0.5, 0.75].map((ratio) => pad.top + plotHeight.value * ratio),
)

const hovered = computed(() => {
  if (hoverIndex.value === null) return null
  return coords.value[hoverIndex.value] || null
})

function formatValue(value: number): string {
  if (props.formatValue) return props.formatValue(value)
  const rounded = Math.abs(value) >= 100 ? Math.round(value) : Math.round(value * 10) / 10
  return `${rounded}${props.unit}`
}

function onPointerMove(event: PointerEvent) {
  if (!container.value || props.points.length === 0) return
  const rect = container.value.getBoundingClientRect()
  const localX = Math.min(Math.max(event.clientX - rect.left, 0), rect.width)
  const ratio = localX / Math.max(1, rect.width)
  const index = Math.round(ratio * (props.points.length - 1))
  hoverIndex.value = Math.min(props.points.length - 1, Math.max(0, index))
}

function clearHover() {
  hoverIndex.value = null
}

const tooltipStyle = computed(() => {
  if (!hovered.value) return {}
  const percent = (hovered.value.x / width.value) * 100
  return {
    left: `${percent}%`,
    transform: percent > 68 ? 'translateX(-108%)' : 'translateX(10px)',
    top: `${Math.max(2, hovered.value.y - 18)}px`,
  }
})
</script>

<template>
  <div class="spark">
    <div class="spark-head">
      <span class="spark-label">{{ label }}</span>
      <span v-if="latest" class="spark-current">{{ formatValue(latest.value) }}</span>
    </div>
    <div
      ref="container"
      class="spark-canvas"
      :style="{ height: `${height}px` }"
      @pointermove="onPointerMove"
      @pointerleave="clearHover"
    >
      <svg
        :width="width"
        :height="height"
        :viewBox="`0 0 ${width} ${height}`"
        role="img"
        :aria-label="`${label}趋势，当前 ${latest ? formatValue(latest.value) : '无数据'}`"
      >
        <defs>
          <linearGradient :id="gradientId" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" :stop-color="color" stop-opacity="0.2" />
            <stop offset="100%" :stop-color="color" stop-opacity="0" />
          </linearGradient>
        </defs>
        <line
          v-for="(y, index) in gridLines"
          :key="index"
          :x1="pad.left"
          :x2="width - pad.right"
          :y1="y"
          :y2="y"
          stroke="rgba(148,178,209,.07)"
          stroke-width="1"
        />
        <path v-if="areaPath" :d="areaPath" :fill="`url(#${gradientId})`" />
        <path
          v-if="linePath"
          :d="linePath"
          fill="none"
          :stroke="color"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <line
          v-if="hovered"
          :x1="hovered.x"
          :x2="hovered.x"
          :y1="pad.top"
          :y2="height - pad.bottom"
          stroke="rgba(148,178,209,.28)"
          stroke-width="1"
        />
        <circle
          v-if="hovered"
          :cx="hovered.x"
          :cy="hovered.y"
          r="4"
          :fill="color"
          stroke="var(--surface-chart)"
          stroke-width="2"
        />
        <circle
          v-if="coords.length"
          :cx="coords[coords.length - 1].x"
          :cy="coords[coords.length - 1].y"
          r="4.5"
          :fill="color"
          stroke="var(--surface-chart)"
          stroke-width="2"
        />
      </svg>
      <div v-if="hovered" class="spark-tooltip" :style="tooltipStyle">
        <span class="spark-tooltip-time">{{ formatTime(hovered.t) }}</span>
        <strong>{{ formatValue(hovered.value) }}</strong>
      </div>
      <div v-if="!points.length" class="spark-empty">等待传感器数据…</div>
    </div>
    <div class="spark-axis">
      <span v-if="points.length">{{ formatTime(points[0].t) }}</span>
      <span v-else>--:--</span>
      <span>现在</span>
    </div>
    <table class="sr-only">
      <caption>{{ label }}数据</caption>
      <thead>
        <tr><th>时间</th><th>数值</th></tr>
      </thead>
      <tbody>
        <tr v-for="point in points.slice(-12)" :key="point.t">
          <td>{{ formatTime(point.t) }}</td>
          <td>{{ formatValue(point.value) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.spark {
  position: relative;
  width: 100%;
  min-width: 0;
}

.spark-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 5px;
}

.spark-label {
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-3);
}

.spark-current {
  font-size: 11.5px;
  font-weight: 550;
  color: var(--text-2);
  font-variant-numeric: tabular-nums;
}

.spark-canvas {
  position: relative;
  width: 100%;
  touch-action: pan-y;
  cursor: crosshair;
}

.spark-canvas svg {
  width: 100%;
  height: 100%;
  overflow: visible;
}

.spark-tooltip {
  position: absolute;
  z-index: 4;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
  border-radius: 7px;
  background: rgba(8, 15, 22, 0.95);
  border: 1px solid var(--line-strong);
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.35);
  pointer-events: none;
  white-space: nowrap;
}

.spark-tooltip-time {
  font-size: 9px;
  color: var(--text-3);
  font-variant-numeric: tabular-nums;
}

.spark-tooltip strong {
  font-size: 11px;
  color: var(--text);
  font-weight: 550;
  font-variant-numeric: tabular-nums;
}

.spark-axis {
  display: flex;
  justify-content: space-between;
  margin-top: 1px;
  font-size: 9px;
  color: var(--text-4);
  font-variant-numeric: tabular-nums;
}

.spark-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-size: 10px;
  color: var(--text-4);
}
</style>
