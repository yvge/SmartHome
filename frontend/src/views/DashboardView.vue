<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  CloudSun,
  Droplets,
  Gauge,
  Loader2,
  MessageSquareText,
  Play,
  RefreshCw,
  Sparkles,
  Sun,
  Thermometer,
  Wind,
  Workflow,
  Zap,
} from 'lucide-vue-next'
import ClimateOrb from '@/components/ClimateOrb.vue'
import Sparkline from '@/components/Sparkline.vue'
import FloorPlan from '@/components/FloorPlan.vue'
import DeviceIcon from '@/components/DeviceIcon.vue'
import { useHomeStore } from '@/stores/home'
import { useSceneStore } from '@/stores/scenes'
import { api } from '@/services/http'
import type { Device, Execution, Scene } from '@/types'
import {
  formatNumber,
  formatTime,
  formatWatt,
  greetingForHour,
  periodGreeting,
  relativeTime,
  statusLabel,
} from '@/utils/format'

const router = useRouter()
const home = useHomeStore()
const scenes = useSceneStore()

const executions = ref<Execution[]>([])
const loadingExecutions = ref(false)
let refreshTimer: number | undefined

const greeting = computed(() => {
  const hour = new Date().getHours()
  return greetingForHour(hour)
})

const dateText = computed(() =>
  new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' }),
)

const activeCount = computed(() => home.activeDevices.length)
const onlineRatio = computed(() =>
  home.devices.length ? Math.round((home.onlineDevices.length / home.devices.length) * 100) : 0,
)

const quickScenes = computed<Scene[]>(() => {
  const preferred = ['scene_arrive', 'scene_movie', 'scene_sleep', 'scene_leave']
  const map = new Map(scenes.scenes.map((scene) => [scene.id, scene]))
  return preferred.map((id) => map.get(id)).filter(Boolean).slice(0, 4) as Scene[]
})

const activeDevices = computed(() =>
  home.activeDevices
    .slice()
    .sort((a, b) => (a.type === 'sensor' ? 1 : 0) - (b.type === 'sensor' ? 1 : 0))
    .slice(0, 6),
)

const airQuality = computed(() => {
  const pm = home.environment.pm25
  if (pm <= 35) return { label: '优', tone: 'good' }
  if (pm <= 75) return { label: '良', tone: 'warn' }
  return { label: '需净化', tone: 'bad' }
})

const humidityLabel = computed(() => {
  const humidity = home.environment.humidity
  if (humidity < 40) return '偏干'
  if (humidity > 65) return '偏湿'
  return '舒适'
})

const lightLabel = computed(() => {
  if (home.environment.lux > 500) return '明亮'
  if (home.environment.lux > 180) return '柔和'
  return '偏暗'
})

const activeRunName = computed(() => {
  if (!scenes.runningSceneId) return ''
  return scenes.activeRun?.name || scenes.sceneById(scenes.runningSceneId)?.name || '场景'
})

const recentPrompts = [
  '帮我把客厅灯调暖一点',
  '如果室内温度高于 26 度就开空调',
  '开启观影模式',
]

async function loadExecutions() {
  loadingExecutions.value = true
  try {
    const response = await api.get<{ executions: Execution[] }>('/system/executions?limit=6')
    executions.value = response.executions
  } catch {
    // dashboard can live without activity history
  } finally {
    loadingExecutions.value = false
  }
}

function openChat(prompt?: string) {
  router.push({ path: '/chat', query: prompt ? { prompt } : undefined })
}

function openScenes() {
  router.push('/scenes')
}

function runScene(scene: Scene) {
  scenes.runScene(scene)
}

async function quickToggle(device: Device) {
  if (!device.online) return
  await home.controlDevice(device.id, { power: !device.properties.power }, { quiet: false })
}

function statusTone(status: string): string {
  if (status === 'success') return 'good'
  if (status === 'partial') return 'warn'
  if (status === 'failed') return 'bad'
  return 'neutral'
}

onMounted(() => {
  loadExecutions()
  refreshTimer = window.setInterval(loadExecutions, 30000)
})

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<template>
  <div class="page dashboard">
    <section class="page-head">
      <div>
        <div class="dash-eyebrow">
          <span>{{ dateText }}</span>
          <span class="sep"></span>
          <span>{{ home.environment.period }} · 全屋 {{ onlineRatio }}% 在线</span>
        </div>
        <h1>{{ greeting }}，欢迎回家</h1>
        <p class="lede">
          小居已接管 {{ home.devices.length }} 台设备，{{ activeCount }} 台正在运行。
          <span class="lede-accent">说一句话，全屋设备与场景会自动协同。</span>
        </p>
      </div>
      <div class="page-actions">
        <div class="weather-chip">
          <CloudSun :size="16" />
          <span class="weather-temp">{{ home.environment.outdoor_temp }}°</span>
          <span class="weather-label">室外 · {{ home.environment.outdoor_weather }}</span>
        </div>
        <button class="btn" @click="openScenes">
          <Workflow :size="15" />
          场景编排
        </button>
        <button class="btn btn-primary" @click="openChat()">
          <Sparkles :size="15" />
          和管家聊聊
        </button>
      </div>
    </section>

    <div class="dash-top">
      <section class="panel climate-panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">Whole Home Climate</div>
            <div class="panel-title">
              全屋环境
              <span class="panel-title-dot"></span>
            </div>
            <div class="panel-desc">由环境模拟器每 4 秒刷新，联动灯光、空调与净化设备</div>
          </div>
          <span class="chip mint"><span class="chip-dot"></span>实时 · {{ formatTime(home.environment.updated_at) }}</span>
        </div>

        <div class="climate-body">
          <ClimateOrb
            :temperature="home.environment.indoor_temp"
            :humidity="home.environment.humidity"
            :comfort="home.comfortLabel"
            :size="228"
          />

          <div class="climate-side">
            <div class="metric-grid">
              <div class="metric">
                <div class="metric-icon mint"><Droplets :size="14" /></div>
                <div class="metric-body">
                  <span class="metric-label">相对湿度</span>
                  <strong>{{ home.environment.humidity }}<em>%</em></strong>
                  <span class="metric-note">{{ humidityLabel }}</span>
                </div>
              </div>
              <div class="metric">
                <div class="metric-icon indigo"><Wind :size="14" /></div>
                <div class="metric-body">
                  <span class="metric-label">空气质量</span>
                  <strong>{{ home.environment.pm25 }}<em>μg/m³</em></strong>
                  <span class="metric-note" :class="airQuality.tone">{{ airQuality.label }}</span>
                </div>
              </div>
              <div class="metric">
                <div class="metric-icon amber"><Zap :size="14" /></div>
                <div class="metric-body">
                  <span class="metric-label">实时功率</span>
                  <strong class="power-value">{{ formatWatt(home.environment.power_w) }}</strong>
                  <span class="metric-note">全屋合计</span>
                </div>
              </div>
              <div class="metric">
                <div class="metric-icon blue"><Sun :size="14" /></div>
                <div class="metric-body">
                  <span class="metric-label">环境光照</span>
                  <strong>{{ home.environment.lux }}<em>lux</em></strong>
                  <span class="metric-note">{{ lightLabel }}</span>
                </div>
              </div>
            </div>

            <div class="chart-row">
              <div class="chart-card">
                <Sparkline
                  :points="home.powerHistory"
                  label="全屋功率"
                  color="#5eead4"
                  :height="64"
                  :format-value="formatWatt"
                />
              </div>
              <div class="chart-card">
                <Sparkline
                  :points="home.tempHistory"
                  label="室温趋势"
                  color="#f8c66a"
                  unit="°C"
                  :height="64"
                  :format-value="(value) => `${value.toFixed(1)}°C`"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="panel scenes-panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">Quick Scenes</div>
            <div class="panel-title">快捷场景</div>
            <div class="panel-desc">LangGraph 多步编排，支持条件与兜底</div>
          </div>
          <button class="icon-btn sm" title="全部场景" @click="openScenes">
            <ArrowUpRight :size="14" />
          </button>
        </div>

        <div class="quick-scenes">
          <button
            v-for="scene in quickScenes"
            :key="scene.id"
            class="quick-scene"
            :disabled="Boolean(scenes.runningSceneId)"
            @click="runScene(scene)"
          >
            <div class="quick-icon">
              <DeviceIcon :icon="scene.icon" :size="18" />
            </div>
            <div class="quick-copy">
              <span class="quick-name">{{ scene.name }}</span>
              <span class="quick-meta">{{ scene.steps.length }} 个动作 · {{ scene.description }}</span>
            </div>
            <span class="quick-play">
              <Loader2 v-if="scenes.runningSceneId === scene.id" :size="13" class="spin" />
              <Play v-else :size="12" />
            </span>
          </button>
          <div v-if="!quickScenes.length" class="empty-state small">场景加载中…</div>
        </div>

        <div class="scene-helper">
          <span class="helper-dot"></span>
          <span v-if="activeRunName">正在执行「{{ activeRunName }}」</span>
          <span v-else>场景会按条件自动跳过动作，关键设备失败时进入兜底分支</span>
          <RouterLink to="/scenes" class="helper-link">查看编排 <ChevronRight :size="11" /></RouterLink>
        </div>
      </section>
    </div>

    <div class="dash-mid">
      <section class="panel floor-panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">Spatial Topology</div>
            <div class="panel-title">空间拓扑</div>
            <div class="panel-desc">点击设备标记可直接查看状态与控制，光晕表示设备正在运行</div>
          </div>
          <div class="floor-meta">
            <span class="chip"><Gauge :size="11" /> {{ home.rooms.length }} 个房间</span>
            <span class="chip mint"><span class="chip-dot"></span>{{ activeCount }} 台运行</span>
          </div>
        </div>
        <FloorPlan
          :devices="home.devices"
          :rooms="home.rooms"
          :room-meta="home.roomMeta"
          :period="home.environment.period"
          :selected-id="home.selectedDeviceId"
          @select="home.selectDevice($event.id)"
        />
      </section>

      <div class="dash-right">
        <section class="panel active-panel">
          <div class="panel-head compact">
            <div>
              <div class="panel-title small">正在运行</div>
              <div class="panel-desc">{{ activeCount }} 台设备处于活跃状态</div>
            </div>
            <RouterLink to="/devices" class="panel-link">全部设备 <ChevronRight :size="12" /></RouterLink>
          </div>

          <div class="active-list">
            <button
              v-for="device in activeDevices"
              :key="device.id"
              class="active-row"
              @click="home.selectDevice(device.id)"
            >
              <div class="active-icon">
                <DeviceIcon :icon="device.icon" :size="15" />
              </div>
              <div class="active-copy">
                <span class="active-name">{{ device.name }}</span>
                <span class="active-state">{{ device.room }} · {{ device.type_label }}</span>
              </div>
              <span class="active-metric">{{ device.properties.brightness ? `${device.properties.brightness}%` : device.type === 'ac' ? `${device.properties.target_temp}°C` : '运行' }}</span>
              <span
                v-if="['light', 'ac', 'purifier', 'socket', 'speaker'].includes(device.type)"
                class="active-toggle"
                role="button"
                tabindex="0"
                @click.stop="quickToggle(device)"
                @keydown.enter.stop="quickToggle(device)"
              >
                <span></span>
              </span>
            </button>
            <div v-if="!activeDevices.length" class="empty-state small">
              当前没有运行中的设备。试试执行「回家模式」。
            </div>
          </div>
        </section>

        <section class="panel activity-panel">
          <div class="panel-head compact">
            <div>
              <div class="panel-title small">最近活动</div>
              <div class="panel-desc">Agent 执行记录</div>
            </div>
            <button class="icon-btn sm" title="刷新" :disabled="loadingExecutions" @click="loadExecutions">
              <RefreshCw :size="12" :class="{ spin: loadingExecutions }" />
            </button>
          </div>

          <div class="activity-list">
            <button
              v-for="execution in executions.slice(0, 4)"
              :key="execution.id"
              class="activity-row"
              @click="router.push('/executions')"
            >
              <span class="activity-dot" :class="statusTone(execution.status)"></span>
              <div class="activity-copy">
                <span class="activity-title">{{ execution.title || execution.input || 'Agent 执行' }}</span>
                <span class="activity-meta">
                  {{ execution.kind === 'scene' ? '场景' : '对话' }} · {{ relativeTime(execution.created_at) }}
                </span>
              </div>
              <span class="activity-result" :class="statusTone(execution.status)">
                {{ statusLabel(execution.status) }}
              </span>
            </button>
            <div v-if="!executions.length" class="empty-state small">
              还没有 Agent 运行记录，去和管家说句话吧。
            </div>
          </div>
          <RouterLink to="/executions" class="activity-foot">
            查看完整运行轨迹 <ArrowUpRight :size="12" />
          </RouterLink>
        </section>
      </div>
    </div>

    <section class="panel ai-strip">
      <div class="ai-intro">
        <div class="ai-orb"><Sparkles :size="18" /></div>
        <div>
          <div class="ai-title">不知道怎么说？试试这些</div>
          <div class="ai-desc">小居会理解你的自然语言，并展示完整的意图识别与工具调用过程</div>
        </div>
      </div>
      <div class="prompt-chips">
        <button
          v-for="prompt in recentPrompts"
          :key="prompt"
          class="prompt-chip"
          @click="openChat(prompt)"
        >
          <MessageSquareText :size="12" />
          {{ prompt }}
        </button>
      </div>
      <div class="ai-capabilities">
        <RouterLink to="/knowledge" class="capability">
          <BookOpen :size="14" />
          <span>RAG 知识问答</span>
          <ChevronRight :size="11" />
        </RouterLink>
        <RouterLink to="/executions" class="capability">
          <Activity :size="14" />
          <span>运行轨迹</span>
          <ChevronRight :size="11" />
        </RouterLink>
        <RouterLink to="/scenes" class="capability">
          <Workflow :size="14" />
          <span>场景编排</span>
          <ChevronRight :size="11" />
        </RouterLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.dash-eyebrow {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 10.5px;
  letter-spacing: 0.1em;
  color: var(--text-3);
  text-transform: uppercase;
  margin-bottom: 7px;
}

.dash-eyebrow .sep {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--text-4);
}

.lede-accent {
  color: var(--text-2);
}

.weather-chip {
  display: flex;
  align-items: center;
  gap: 7px;
  height: 38px;
  padding: 0 13px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.025);
  color: var(--text-2);
}

.weather-temp {
  font-size: 14px;
  font-weight: 550;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.weather-label {
  font-size: 10px;
  color: var(--text-3);
}

.dash-top {
  display: grid;
  grid-template-columns: minmax(0, 1.52fr) minmax(0, 0.8fr);
  gap: 18px;
}

.dash-top > *,
.dash-mid > * {
  min-width: 0;
}

.climate-panel,
.scenes-panel {
  min-height: 318px;
  padding: 20px;
}

.climate-body {
  display: flex;
  align-items: center;
  gap: 18px;
}

.climate-side {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 13px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  min-width: 0;
}

.metric {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px;
  border-radius: 11px;
  border: 1px solid rgba(148, 178, 209, 0.075);
  background: rgba(255, 255, 255, 0.022);
  min-width: 0;
}

.metric-icon {
  width: 27px;
  height: 27px;
  flex: 0 0 27px;
  border-radius: 8px;
  display: grid;
  place-items: center;
}

.metric-icon.mint {
  color: var(--mint);
  background: var(--mint-soft);
}

.metric-icon.indigo {
  color: var(--indigo);
  background: var(--indigo-soft);
}

.metric-icon.amber {
  color: var(--amber);
  background: var(--amber-soft);
}

.metric-icon.blue {
  color: #7dd3fc;
  background: rgba(125, 211, 252, 0.09);
}

.metric-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.metric-label {
  font-size: 9px;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--text-4);
  white-space: nowrap;
}

.metric-body strong {
  font-size: 16px;
  font-weight: 550;
  color: var(--text);
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.metric-body strong em {
  font-style: normal;
  font-size: 8.5px;
  color: var(--text-4);
  margin-left: 2px;
  font-weight: 400;
}

.metric-body strong.power-value {
  font-size: 14px;
}

.metric-note {
  font-size: 8.5px;
  color: var(--text-4);
  white-space: nowrap;
}

.metric-note.good {
  color: var(--good);
}

.metric-note.warn {
  color: var(--warning);
}

.metric-note.bad {
  color: var(--critical);
}

.chart-row {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 8px;
}

.chart-card {
  padding: 9px 10px 6px;
  border-radius: 11px;
  border: 1px solid rgba(148, 178, 209, 0.07);
  background: rgba(5, 11, 18, 0.28);
  min-width: 0;
}

.panel-title-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--mint);
  box-shadow: 0 0 9px rgba(94, 234, 212, 0.8);
  margin-left: 2px;
}

.quick-scenes {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
}

.quick-scene {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 11px;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.022);
  text-align: left;
  min-width: 0;
  transition:
    background 0.17s ease,
    border-color 0.17s ease,
    transform 0.17s ease;
}

.quick-scene:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.045);
  border-color: var(--line);
  transform: translateX(2px);
}

.quick-scene:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.quick-icon {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  color: var(--mint);
  background: rgba(94, 234, 212, 0.065);
  border: 1px solid rgba(94, 234, 212, 0.1);
}

.quick-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.quick-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text);
}

.quick-meta {
  font-size: 9.5px;
  color: var(--text-4);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quick-play {
  width: 24px;
  height: 24px;
  flex: 0 0 24px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: var(--text-3);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--line);
  transition: color 0.16s ease, background 0.16s ease;
}

.quick-scene:hover .quick-play {
  color: #06211d;
  background: var(--mint);
  border-color: transparent;
}

.scene-helper {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 13px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
  font-size: 9.5px;
  color: var(--text-4);
  min-width: 0;
}

.scene-helper > span:not(.helper-dot) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.helper-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--mint);
  flex: 0 0 4px;
}

.helper-link {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 1px;
  color: var(--text-3);
  white-space: nowrap;
}

.helper-link:hover {
  color: var(--mint);
}

.dash-mid {
  display: grid;
  grid-template-columns: minmax(0, 1.52fr) minmax(0, 0.8fr);
  gap: 18px;
  align-items: stretch;
}

.floor-panel {
  padding: 22px;
  display: flex;
  flex-direction: column;
}

.floor-meta {
  display: flex;
  align-items: center;
  gap: 7px;
}

.dash-right {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
}

.active-panel,
.activity-panel {
  padding: 18px;
}

.panel-head.compact {
  margin-bottom: 10px;
  align-items: center;
}

.panel-title.small {
  font-size: 14px;
}

.panel-link {
  display: inline-flex;
  align-items: center;
  gap: 1px;
  font-size: 10px;
  color: var(--text-3);
  white-space: nowrap;
}

.panel-link:hover {
  color: var(--mint);
}

.active-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.active-row {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 6px;
  border-radius: 9px;
  border: none;
  background: transparent;
  text-align: left;
  width: 100%;
  transition: background 0.16s ease;
}

.active-row:hover {
  background: rgba(255, 255, 255, 0.035);
}

.active-icon {
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: var(--mint);
  background: rgba(94, 234, 212, 0.06);
}

.active-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.active-name {
  font-size: 11.5px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.active-state {
  font-size: 9px;
  color: var(--text-4);
}

.active-metric {
  font-size: 10px;
  color: var(--text-2);
  font-variant-numeric: tabular-nums;
  margin-right: 2px;
}

.active-toggle {
  width: 26px;
  height: 16px;
  flex: 0 0 26px;
  border-radius: 99px;
  background: var(--mint-soft);
  border: 1px solid rgba(94, 234, 212, 0.2);
  position: relative;
}

.active-toggle span {
  position: absolute;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  right: 3px;
  top: 50%;
  transform: translateY(-50%);
  background: var(--mint);
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.activity-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 6px;
  border: none;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  width: 100%;
  transition: background 0.16s ease;
}

.activity-row:hover {
  background: rgba(255, 255, 255, 0.03);
}

.activity-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex: 0 0 5px;
  margin-top: 5px;
  background: var(--text-4);
}

.activity-dot.good {
  background: var(--good);
  box-shadow: 0 0 7px rgba(85, 217, 154, 0.55);
}

.activity-dot.warn {
  background: var(--warning);
}

.activity-dot.bad {
  background: var(--critical);
}

.activity-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.activity-title {
  font-size: 10.5px;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-meta {
  font-size: 9px;
  color: var(--text-4);
}

.activity-result {
  font-size: 8.5px;
  white-space: nowrap;
  color: var(--text-4);
}

.activity-result.good {
  color: var(--good);
}

.activity-result.warn {
  color: var(--warning);
}

.activity-result.bad {
  color: var(--critical);
}

.activity-foot {
  margin-top: 8px;
  padding-top: 9px;
  border-top: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 9.5px;
  color: var(--text-3);
}

.activity-foot:hover {
  color: var(--mint);
}

.ai-strip {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 16px 20px;
  flex-wrap: wrap;
}

.ai-intro {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 260px;
}

.ai-orb {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  color: var(--mint);
  background: linear-gradient(140deg, rgba(94, 234, 212, 0.14), rgba(139, 149, 248, 0.12));
  border: 1px solid rgba(94, 234, 212, 0.17);
  box-shadow: 0 0 24px rgba(94, 234, 212, 0.08);
}

.ai-title {
  font-size: 12px;
  font-weight: 550;
}

.ai-desc {
  font-size: 9.5px;
  color: var(--text-4);
}

.prompt-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  flex: 1;
}

.prompt-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.022);
  color: var(--text-3);
  font-size: 10px;
  transition: all 0.16s ease;
  white-space: nowrap;
}

.prompt-chip:hover {
  color: var(--mint);
  border-color: rgba(94, 234, 212, 0.22);
  background: var(--mint-soft);
}

.ai-capabilities {
  display: flex;
  gap: 4px;
}

.capability {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 8px;
  border-radius: 8px;
  color: var(--text-4);
  font-size: 9.5px;
  transition: color 0.16s ease, background 0.16s ease;
}

.capability:hover {
  color: var(--text-2);
  background: rgba(255, 255, 255, 0.03);
}

.spin {
  animation: spin 0.9s linear infinite;
}

.empty-state.small {
  padding: 22px 10px;
  font-size: 10.5px;
}

@media (max-width: 1280px) {
  .dash-top,
  .dash-mid {
    grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.85fr);
  }

  .chart-row {
    grid-template-columns: 1fr;
  }

  .climate-body {
    align-items: flex-start;
  }
}

@media (max-width: 1100px) {
  .dash-top,
  .dash-mid {
    grid-template-columns: minmax(0, 1fr);
  }

  .climate-body {
    align-items: center;
  }

  .chart-row {
    grid-template-columns: 1fr 1fr;
  }

  .dash-right {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .dashboard {
    gap: 14px;
  }

  .page-actions {
    width: 100%;
  }

  .weather-chip {
    height: 34px;
  }

  .climate-body {
    flex-direction: column;
    align-items: stretch;
  }

  .climate-side {
    gap: 10px;
  }

  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .chart-row {
    grid-template-columns: 1fr;
  }

  .dash-right {
    display: flex;
  }

  .ai-strip {
    padding: 14px;
    gap: 12px;
  }

  .ai-capabilities {
    display: none;
  }

  .ai-intro {
    min-width: 0;
  }
}
</style>
