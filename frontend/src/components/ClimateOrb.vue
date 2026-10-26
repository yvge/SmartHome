<script setup lang="ts">
import { computed } from 'vue'
import { clamp } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    temperature: number
    comfort?: string
    humidity?: number
    size?: number
  }>(),
  { comfort: '体感舒适', humidity: 0, size: 236 },
)

const radius = 86
const circumference = 2 * Math.PI * radius
const arcLength = circumference * 0.75
const startAngle = 135

const fraction = computed(() => clamp((props.temperature - 16) / 16, 0, 1))
const dash = computed(() => `${(arcLength * fraction.value).toFixed(2)} ${circumference.toFixed(2)}`)

const palette = computed(() => {
  if (props.temperature >= 28) return { from: '#c08a3e', to: '#b96a45', glow: 'rgba(192, 138, 62, 0.22)' }
  if (props.temperature <= 21) return { from: '#5f6b52', to: '#b44a26', glow: 'rgba(95, 107, 82, 0.2)' }
  return { from: '#b44a26', to: '#5f6b52', glow: 'rgba(180, 74, 38, 0.2)' }
})

const endPoint = computed(() => {
  const angle = ((startAngle + 270 * fraction.value) * Math.PI) / 180
  return {
    x: 110 + radius * Math.cos(angle),
    y: 110 + radius * Math.sin(angle),
  }
})

const ticks = computed(() =>
  Array.from({ length: 9 }, (_, index) => {
    const angle = ((startAngle + (270 / 8) * index) * Math.PI) / 180
    const inner = radius + 9
    const outer = radius + (index % 2 === 0 ? 15 : 12)
    return {
      x1: 110 + inner * Math.cos(angle),
      y1: 110 + inner * Math.sin(angle),
      x2: 110 + outer * Math.cos(angle),
      y2: 110 + outer * Math.sin(angle),
      major: index % 2 === 0,
    }
  }),
)
</script>

<template>
  <div class="climate-orb" :style="{ width: `${size}px`, height: `${size}px`, '--orb-glow': palette.glow }">
    <div class="orb-halo"></div>
    <svg viewBox="0 0 220 220" class="orb-svg" role="img" :aria-label="`室内温度 ${temperature} 摄氏度，${comfort}`">
      <defs>
        <linearGradient id="climateArc" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" :stop-color="palette.from" />
          <stop offset="100%" :stop-color="palette.to" />
        </linearGradient>
        <radialGradient id="orbInner" cx="50%" cy="42%" r="60%">
          <stop offset="0%" stop-color="rgba(180, 74, 38, 0.04)" />
          <stop offset="70%" stop-color="rgba(180, 74, 38, 0.01)" />
          <stop offset="100%" stop-color="transparent" />
        </radialGradient>
      </defs>
      <circle cx="110" cy="110" r="72" fill="url(#orbInner)" />
      <circle
        cx="110"
        cy="110"
        :r="radius"
        fill="none"
        stroke="rgba(41, 37, 36, 0.1)"
        stroke-width="7"
        :stroke-dasharray="`${arcLength} ${circumference}`"
        stroke-linecap="round"
        :transform="`rotate(${startAngle} 110 110)`"
      />
      <circle
        cx="110"
        cy="110"
        :r="radius"
        fill="none"
        stroke="url(#climateArc)"
        stroke-width="7"
        :stroke-dasharray="dash"
        stroke-linecap="round"
        :transform="`rotate(${startAngle} 110 110)`"
        class="arc-value"
      />
      <g class="ticks">
        <line
          v-for="(tick, index) in ticks"
          :key="index"
          :x1="tick.x1"
          :y1="tick.y1"
          :x2="tick.x2"
          :y2="tick.y2"
          :stroke="tick.major ? 'rgba(41, 37, 36, 0.32)' : 'rgba(41, 37, 36, 0.16)'"
          stroke-width="1"
          stroke-linecap="round"
        />
      </g>
      <circle
        :cx="endPoint.x"
        :cy="endPoint.y"
        r="4.5"
        fill="var(--mint)"
        stroke="#fffdf9"
        stroke-width="2.5"
        class="arc-end"
      />
    </svg>
    <div class="orb-center">
      <div class="orb-label">室内温度</div>
      <div class="orb-value">
        {{ temperature.toFixed(1) }}<span>°C</span>
      </div>
      <div class="orb-comfort"><i></i>{{ comfort }}</div>
      <div v-if="humidity" class="orb-sub">湿度 {{ humidity }}%</div>
    </div>
  </div>
</template>

<style scoped>
.climate-orb {
  position: relative;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
}

.orb-halo {
  display: none;
}

.orb-svg {
  width: 100%;
  height: 100%;
  position: relative;
  z-index: 1;
  overflow: visible;
}

.arc-value {
  filter: none;
}

.arc-end {
  filter: none;
}

.ticks {
  opacity: 0.9;
}

.orb-center {
  position: absolute;
  inset: 22%;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.orb-label {
  font-size: 10.5px;
  letter-spacing: 0.14em;
  color: var(--text-3);
  margin-bottom: 4px;
}

.orb-value {
  font-family: var(--font-serif);
  font-size: clamp(40px, 4.1vw, 52px);
  font-weight: 500;
  letter-spacing: -0.035em;
  line-height: 1;
  font-variant-numeric: lining-nums;
}

.orb-value span {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 400;
  letter-spacing: 0;
  color: var(--text-3);
  margin-left: 3px;
}

.orb-comfort {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 11px;
  font-size: 10.5px;
  color: var(--mint);
}

.orb-comfort i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
}

.orb-sub {
  font-size: 10.5px;
  color: var(--text-4);
  margin-top: 8px;
  font-variant-numeric: tabular-nums;
}
</style>
