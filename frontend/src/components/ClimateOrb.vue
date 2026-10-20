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
  if (props.temperature >= 28) return { from: '#f8c66a', to: '#f0946c', glow: 'rgba(248,198,106,.22)' }
  if (props.temperature <= 21) return { from: '#8b95f8', to: '#5eead4', glow: 'rgba(139,149,248,.2)' }
  return { from: '#5eead4', to: '#8b95f8', glow: 'rgba(94,234,212,.2)' }
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
          <stop offset="0%" stop-color="rgba(94,234,212,.08)" />
          <stop offset="70%" stop-color="rgba(94,234,212,.015)" />
          <stop offset="100%" stop-color="transparent" />
        </radialGradient>
      </defs>
      <circle cx="110" cy="110" r="72" fill="url(#orbInner)" />
      <circle
        cx="110"
        cy="110"
        :r="radius"
        fill="none"
        stroke="rgba(148,178,209,.1)"
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
          :stroke="tick.major ? 'rgba(148,178,209,.32)' : 'rgba(148,178,209,.16)'"
          stroke-width="1"
          stroke-linecap="round"
        />
      </g>
      <circle
        :cx="endPoint.x"
        :cy="endPoint.y"
        r="5.5"
        fill="#eafffb"
        stroke="var(--surface-chart)"
        stroke-width="3"
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
  position: absolute;
  inset: 17%;
  border-radius: 50%;
  background: var(--orb-glow);
  filter: blur(28px);
  opacity: 0.9;
  animation: pulse-soft 6s ease-in-out infinite;
}

.orb-svg {
  width: 100%;
  height: 100%;
  position: relative;
  z-index: 1;
  overflow: visible;
}

.arc-value {
  filter: drop-shadow(0 0 7px rgba(94, 234, 212, 0.3));
}

.arc-end {
  filter: drop-shadow(0 0 8px rgba(94, 234, 212, 0.55));
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
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-3);
  margin-bottom: 3px;
}

.orb-value {
  font-family: var(--font-display);
  font-size: clamp(38px, 4vw, 50px);
  font-weight: 580;
  letter-spacing: -0.05em;
  line-height: 1;
  font-variant-numeric: proportional-nums;
}

.orb-value span {
  font-size: 17px;
  font-weight: 500;
  letter-spacing: 0;
  color: var(--text-2);
  margin-left: 3px;
}

.orb-comfort {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-top: 9px;
  padding: 3px 8px;
  border-radius: 99px;
  font-size: 10px;
  color: var(--mint);
  background: rgba(94, 234, 212, 0.07);
  border: 1px solid rgba(94, 234, 212, 0.13);
}

.orb-comfort i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 7px currentColor;
}

.orb-sub {
  font-size: 10px;
  color: var(--text-4);
  margin-top: 7px;
  font-variant-numeric: tabular-nums;
}
</style>
