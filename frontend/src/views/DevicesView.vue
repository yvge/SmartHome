<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Boxes,
  Cpu,
  Network,
  RefreshCw,
  RotateCcw,
  Search,
  Wifi,
  WifiOff,
  Zap,
} from 'lucide-vue-next'
import DeviceCard from '@/components/DeviceCard.vue'
import { useHomeStore } from '@/stores/home'
import { useUiStore } from '@/stores/ui'
import type { Device } from '@/types'
import { formatWatt } from '@/utils/format'

const home = useHomeStore()
const ui = useUiStore()

const roomFilter = ref('all')
const typeFilter = ref('all')
const search = ref('')

const types = computed(() => {
  const map = new Map<string, string>()
  for (const device of home.devices) map.set(device.type, device.type_label)
  return Array.from(map.entries()).map(([value, label]) => ({ value, label }))
})

const filteredDevices = computed(() => {
  const needle = search.value.trim().toLowerCase()
  return home.devices.filter((device) => {
    if (roomFilter.value !== 'all' && device.room_id !== roomFilter.value) return false
    if (typeFilter.value !== 'all' && device.type !== typeFilter.value) return false
    if (needle && !`${device.name}${device.room}${device.type_label}`.toLowerCase().includes(needle)) {
      return false
    }
    return true
  })
})

const groupedRooms = computed(() => {
  return home.roomMeta
    .map((room) => ({
      ...room,
      climate: home.rooms.find((item) => item.id === room.id),
      devices: filteredDevices.value.filter((device) => device.room_id === room.id),
    }))
    .filter((room) => room.devices.length > 0)
})

const offlineCount = computed(() => home.offlineDevices.length)

async function toggleDevice(device: Device, value: boolean) {
  if (!device.online) {
    ui.warning(`${device.name} 处于离线状态`)
    return
  }
  await home.controlDevice(device.id, { power: value })
}

function selectDevice(device: Device) {
  home.selectDevice(device.id)
}

async function resetDevices() {
  const confirmed = await ui.askConfirm(
    '将所有设备恢复到演示初始状态？当前设备状态会被覆盖。',
    '重置演示设备',
    true,
  )
  if (!confirmed) return
  await home.resetDevices()
}

function clearFilters() {
  roomFilter.value = 'all'
  typeFilter.value = 'all'
  search.value = ''
}
</script>

<template>
  <div class="page devices-page">
    <section class="page-head">
      <div>
        <div class="eyebrow">Unified Device Access</div>
        <h1>全屋设备</h1>
        <p class="lede">
          {{ home.devices.length }} 台设备通过统一能力 Schema 接入，支持灯光、空调、窗帘、净化、插座等
          {{ types.length }} 类异构硬件。点击卡片查看完整控制面板。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" @click="home.refreshSnapshot()">
          <RefreshCw :size="14" />
          刷新状态
        </button>
        <button class="btn" @click="resetDevices">
          <RotateCcw :size="14" />
          重置演示
        </button>
      </div>
    </section>

    <section class="stat-strip">
      <div class="stat-tile">
        <div class="stat-icon mint"><Wifi :size="15" /></div>
        <div>
          <span class="stat-label">在线设备</span>
          <strong>{{ home.onlineDevices.length }} <em>/ {{ home.devices.length }}</em></strong>
        </div>
        <span class="stat-note">{{ Math.round((home.onlineDevices.length / Math.max(1, home.devices.length)) * 100) }}%</span>
      </div>
      <div class="stat-tile">
        <div class="stat-icon indigo"><Boxes :size="15" /></div>
        <div>
          <span class="stat-label">运行中</span>
          <strong>{{ home.activeDevices.length }} <em>台</em></strong>
        </div>
        <span class="stat-note">活跃</span>
      </div>
      <div class="stat-tile">
        <div class="stat-icon amber"><Zap :size="15" /></div>
        <div>
          <span class="stat-label">实时功率</span>
          <strong>{{ formatWatt(home.environment.power_w) }}</strong>
        </div>
        <span class="stat-note">全屋</span>
      </div>
      <div class="stat-tile">
        <div class="stat-icon" :class="offlineCount ? 'rose' : 'muted'"><WifiOff :size="15" /></div>
        <div>
          <span class="stat-label">离线设备</span>
          <strong>{{ offlineCount }} <em>台</em></strong>
        </div>
        <span class="stat-note" :class="{ warn: offlineCount }">{{ offlineCount ? '需检查' : '全部正常' }}</span>
      </div>
    </section>

    <section class="filter-bar">
      <div class="room-tabs">
        <button
          class="room-tab"
          :class="{ active: roomFilter === 'all' }"
          @click="roomFilter = 'all'"
        >
          全部房间
          <span>{{ home.devices.length }}</span>
        </button>
        <button
          v-for="room in home.roomMeta"
          :key="room.id"
          class="room-tab"
          :class="{ active: roomFilter === room.id }"
          @click="roomFilter = room.id"
        >
          {{ room.name }}
          <span>{{ home.devicesByRoom(room.id).length }}</span>
        </button>
      </div>

      <div class="filter-right">
        <div class="search-box">
          <Search :size="13" />
          <input v-model="search" placeholder="搜索设备" aria-label="搜索设备" />
        </div>
        <select v-model="typeFilter" class="select type-select" aria-label="按类型筛选">
          <option value="all">全部类型</option>
          <option v-for="type in types" :key="type.value" :value="type.value">{{ type.label }}</option>
        </select>
        <button
          v-if="roomFilter !== 'all' || typeFilter !== 'all' || search"
          class="icon-btn sm"
          title="清除筛选"
          @click="clearFilters"
        >
          <RotateCcw :size="12" />
        </button>
      </div>
    </section>

    <div v-if="!home.ready" class="device-skeletons">
      <div v-for="index in 8" :key="index" class="skeleton skeleton-card"></div>
    </div>

    <template v-else-if="filteredDevices.length">
      <section v-if="roomFilter === 'all'" class="room-section" v-for="room in groupedRooms" :key="room.id">
        <header class="room-section-head">
          <div class="room-section-title">
            <span class="room-avatar"><Cpu :size="13" /></span>
            {{ room.name }}
            <span class="room-section-count">{{ room.devices.length }} 台</span>
          </div>
          <div class="room-section-meta">
            <span v-if="room.climate">{{ room.climate.temperature }}°C · {{ room.climate.humidity }}%</span>
            <span class="room-line"></span>
          </div>
        </header>
        <div class="device-grid">
          <DeviceCard
            v-for="device in room.devices"
            :key="device.id"
            :device="device"
            @select="selectDevice"
            @toggle="toggleDevice"
          />
        </div>
      </section>

      <section v-else class="device-grid">
        <DeviceCard
          v-for="device in filteredDevices"
          :key="device.id"
          :device="device"
          @select="selectDevice"
          @toggle="toggleDevice"
        />
      </section>
    </template>

    <div v-else class="panel empty-state">
      <div class="empty-icon"><Search :size="19" /></div>
      <div>没有找到符合条件的设备</div>
      <button class="btn btn-sm" @click="clearFilters">清除筛选条件</button>
    </div>

    <section class="panel schema-panel">
      <div class="schema-copy">
        <div class="schema-icon"><Network :size="17" /></div>
        <div>
          <div class="schema-title">标准化异构设备接入</div>
          <div class="schema-desc">
            每个设备类型都声明可写能力与取值范围，自动映射为 Function Calling 的 JSON Schema；
            同一套工具调用同时驱动真实适配器与模拟器。
          </div>
        </div>
      </div>
      <div class="schema-stats">
        <div><strong>{{ types.length }}</strong><span>设备类型</span></div>
        <div><strong>10</strong><span>工具 Schema</span></div>
        <div><strong>2</strong><span>接入通道</span></div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.devices-page {
  display: flex;
  flex-direction: column;
  gap: 17px;
}

.stat-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.stat-tile {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 13px 14px;
  border-radius: 13px;
  border: 1px solid var(--line);
  background:
    radial-gradient(circle at 100% 0%, rgba(255, 255, 255, 0.025), transparent 55%),
    rgba(15, 24, 36, 0.55);
}

.stat-icon {
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border-radius: 9px;
  display: grid;
  place-items: center;
}

.stat-icon.mint {
  color: var(--mint);
  background: var(--mint-soft);
}

.stat-icon.indigo {
  color: var(--indigo);
  background: var(--indigo-soft);
}

.stat-icon.amber {
  color: var(--amber);
  background: var(--amber-soft);
}

.stat-icon.rose {
  color: var(--critical);
  background: var(--critical-soft);
}

.stat-icon.muted {
  color: var(--text-4);
  background: rgba(255, 255, 255, 0.03);
}

.stat-tile > div:nth-child(2) {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.stat-label {
  font-size: 8.5px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-4);
}

.stat-tile strong {
  font-size: 16px;
  font-weight: 550;
  color: var(--text);
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.stat-tile strong em {
  font-style: normal;
  font-size: 9px;
  color: var(--text-4);
  font-weight: 400;
}

.stat-note {
  margin-left: auto;
  font-size: 8.5px;
  color: var(--text-4);
  white-space: nowrap;
}

.stat-note.warn {
  color: var(--warning);
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.room-tabs {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  padding-bottom: 2px;
  scrollbar-width: none;
}

.room-tabs::-webkit-scrollbar {
  display: none;
}

.room-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-3);
  font-size: 11px;
  white-space: nowrap;
  transition: all 0.16s ease;
}

.room-tab:hover {
  color: var(--text-2);
  background: rgba(255, 255, 255, 0.03);
}

.room-tab.active {
  color: var(--text);
  background: rgba(255, 255, 255, 0.045);
  border-color: var(--line);
}

.room-tab span {
  font-size: 8px;
  color: var(--text-4);
  background: rgba(255, 255, 255, 0.04);
  border-radius: 4px;
  min-width: 15px;
  height: 15px;
  display: inline-grid;
  place-items: center;
  font-variant-numeric: tabular-nums;
}

.filter-right {
  display: flex;
  align-items: center;
  gap: 7px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 10px;
  border-radius: 9px;
  border: 1px solid var(--line);
  background: rgba(5, 11, 18, 0.45);
  color: var(--text-4);
}

.search-box input {
  width: 120px;
  border: none;
  background: transparent;
  outline: none;
  color: var(--text);
  font-size: 10.5px;
}

.search-box input::placeholder {
  color: var(--text-4);
}

.type-select {
  width: 106px;
  height: 32px;
  padding: 0 28px 0 10px;
  font-size: 10.5px;
  border-radius: 9px;
  background-position: right 9px center;
}

.room-section {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.room-section-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 2px;
}

.room-section-title {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11.5px;
  font-weight: 550;
  color: var(--text-2);
  white-space: nowrap;
}

.room-avatar {
  width: 24px;
  height: 24px;
  border-radius: 7px;
  display: grid;
  place-items: center;
  color: var(--text-3);
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid var(--line);
}

.room-section-count {
  font-size: 8.5px;
  font-weight: 400;
  color: var(--text-4);
}

.room-section-meta {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 8.5px;
  color: var(--text-4);
  font-variant-numeric: tabular-nums;
}

.room-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, var(--line), transparent);
}

.device-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(212px, 1fr));
  gap: 10px;
}

.device-skeletons {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(212px, 1fr));
  gap: 10px;
}

.skeleton-card {
  height: 164px;
  border-radius: 17px;
}

.schema-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  padding: 16px 18px;
  flex-wrap: wrap;
}

.schema-copy {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  max-width: 640px;
}

.schema-icon {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  color: var(--indigo);
  background: var(--indigo-soft);
}

.schema-title {
  font-size: 12px;
  font-weight: 550;
}

.schema-desc {
  font-size: 10px;
  line-height: 1.6;
  color: var(--text-4);
  margin-top: 2px;
}

.schema-stats {
  display: flex;
  gap: 22px;
}

.schema-stats > div {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.schema-stats strong {
  font-size: 18px;
  font-weight: 560;
  color: var(--text);
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.schema-stats span {
  font-size: 8.5px;
  color: var(--text-4);
}

@media (max-width: 1000px) {
  .stat-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-bar {
    align-items: flex-start;
    flex-direction: column;
  }

  .room-tabs {
    width: 100%;
  }
}

@media (max-width: 760px) {
  .stat-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .stat-tile {
    padding: 10px;
    gap: 8px;
  }

  .stat-icon {
    width: 28px;
    height: 28px;
    flex-basis: 28px;
  }

  .filter-right {
    width: 100%;
  }

  .search-box {
    flex: 1;
  }

  .search-box input {
    width: 100%;
  }

  .type-select {
    width: 98px;
  }

  .device-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .schema-panel {
    align-items: flex-start;
  }

  .schema-stats {
    width: 100%;
    justify-content: space-between;
  }
}

@media (max-width: 430px) {
  .device-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
