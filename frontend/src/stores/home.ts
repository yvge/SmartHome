import { defineStore } from 'pinia'
import type {
  Device,
  Environment,
  HistoryPoint,
  RoomClimate,
  RoomMeta,
  Snapshot,
  SystemStatus,
} from '@/types'
import { API_BASE, api } from '@/services/http'
import { useUiStore } from '@/stores/ui'

const HISTORY_KEY = 'smarthome.history.v1'
const MAX_POINTS = 40

let eventSource: EventSource | null = null
let reconnectTimer: number | null = null
let reconnectAttempts = 0
let statusTimer: number | null = null
let historyHydrated = false

const EMPTY_ENVIRONMENT: Environment = {
  indoor_temp: 26.4,
  humidity: 52,
  pm25: 21,
  co2: 620,
  lux: 420,
  outdoor_temp: 30,
  outdoor_weather: '晴',
  power_w: 0,
  period: '午后',
  updated_at: new Date().toISOString(),
}

function seedSeries(base: number, spread: number, count = 24): HistoryPoint[] {
  const now = Date.now()
  return Array.from({ length: count }, (_, index) => ({
    t: now - (count - 1 - index) * 5000,
    value:
      Math.round(
        (base +
          Math.sin(index * 0.62) * spread +
          Math.cos(index * 0.21) * spread * 0.45) * 10,
      ) / 10,
  }))
}

function loadHistory(): { temp: HistoryPoint[]; power: HistoryPoint[] } | null {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as { temp?: HistoryPoint[]; power?: HistoryPoint[] }
    const cutoff = Date.now() - 3_600_000 * 3
    const temp = (parsed.temp || []).filter((point) => point.t > cutoff)
    const power = (parsed.power || []).filter((point) => point.t > cutoff)
    if (temp.length < 5 || power.length < 5) return null
    return { temp: temp.slice(-MAX_POINTS), power: power.slice(-MAX_POINTS) }
  } catch {
    return null
  }
}

function saveHistory(temp: HistoryPoint[], power: HistoryPoint[]) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify({ temp, power }))
  } catch {
    // storage may be unavailable; history is non-critical
  }
}

function isDeviceActive(device: Device): boolean {
  const p = device.properties
  switch (device.type) {
    case 'light':
    case 'ac':
    case 'purifier':
    case 'humidifier':
    case 'vacuum':
      return Boolean(p.power)
    case 'socket':
      return Boolean(p.power)
    case 'speaker':
      return Boolean(p.playing)
    case 'curtain':
      return Number(p.position) > 0
    default:
      return false
  }
}

export const useHomeStore = defineStore('home', {
  state: () => ({
    devices: [] as Device[],
    environment: { ...EMPTY_ENVIRONMENT } as Environment,
    rooms: [] as RoomClimate[],
    roomMeta: [] as RoomMeta[],
    status: null as SystemStatus | null,
    connected: false,
    loading: true,
    ready: false,
    error: null as string | null,
    lastUpdated: '',
    tempHistory: [] as HistoryPoint[],
    powerHistory: [] as HistoryPoint[],
    selectedDeviceId: null as string | null,
  }),
  getters: {
    onlineDevices(state): Device[] {
      return state.devices.filter((device) => device.online)
    },
    offlineDevices(state): Device[] {
      return state.devices.filter((device) => !device.online)
    },
    activeDevices(state): Device[] {
      return state.devices.filter((device) => device.online && isDeviceActive(device))
    },
    devicesByRoom(state) {
      return (roomId: string): Device[] =>
        state.devices
          .filter((device) => device.room_id === roomId)
          .sort((a, b) => a.sort_order - b.sort_order)
    },
    roomsWithDevices(state): Array<RoomMeta & { devices: Device[]; climate?: RoomClimate }> {
      return state.roomMeta.map((room) => ({
        ...room,
        devices: state.devices.filter((device) => device.room_id === room.id),
        climate: state.rooms.find((item) => item.id === room.id),
      }))
    },
    selectedDevice(state): Device | null {
      if (!state.selectedDeviceId) return null
      return state.devices.find((device) => device.id === state.selectedDeviceId) || null
    },
    comfortLabel(state): string {
      const temp = state.environment.indoor_temp
      const humidity = state.environment.humidity
      if (temp >= 22 && temp <= 27 && humidity >= 35 && humidity <= 65) return '体感舒适'
      if (temp > 28) return '略显闷热'
      if (temp < 20) return '有点凉爽'
      return '湿度偏低'
    },
    modeLabel(state): string {
      if (!state.status) return '连接中'
      return state.status.llm.enabled ? state.status.llm.model : '离线规则引擎'
    },
    ragLabel(state): string {
      const backend = state.status?.rag.backend
      if (backend === 'milvus') return 'Milvus'
      if (backend === 'local') return '本地向量库'
      return '向量库'
    },
    activeSceneCount(): number {
      return 0
    },
  },
  actions: {
    async bootstrap() {
      const ui = useUiStore()
      this.loading = true
      try {
        const [snapshot, status] = await Promise.all([
          api.get<Snapshot>('/devices'),
          api.get<SystemStatus>('/system/status'),
        ])
        this.applySnapshot(snapshot)
        this.status = status
        this.ready = true
        this.error = null
        this.connectEvents()
        this.startStatusPolling()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '无法连接后端服务'
        this.loading = false
        ui.error(this.error)
        this.scheduleReconnect()
      }
    },
    applySnapshot(snapshot: Snapshot) {
      if (!snapshot) return
      this.devices = snapshot.devices || []
      this.environment = snapshot.environment || { ...EMPTY_ENVIRONMENT }
      this.rooms = snapshot.rooms || []
      if (snapshot.room_meta?.length) this.roomMeta = snapshot.room_meta
      this.lastUpdated = snapshot.timestamp || new Date().toISOString()
      this.loading = false
      this.ready = true
      this.pushHistory()
    },
    pushHistory() {
      if (!this.tempHistory.length || !historyHydrated) {
        const stored = historyHydrated ? null : loadHistory()
        if (stored) {
          this.tempHistory = stored.temp
          this.powerHistory = stored.power
        } else {
          this.tempHistory = seedSeries(this.environment.indoor_temp, 0.32, 24)
          this.powerHistory = seedSeries(
            Math.max(180, this.environment.power_w || 1080),
            Math.max(30, (this.environment.power_w || 1080) * 0.045),
            24,
          )
        }
        historyHydrated = true
      }
      const now = Date.now()
      const tempValue = Number(this.environment.indoor_temp) || 26
      const powerValue = Number(this.environment.power_w) || 0
      const append = (series: HistoryPoint[], value: number) => {
        const next = [...series]
        const last = next[next.length - 1]
        if (last && now - last.t < 2600) next[next.length - 1] = { t: now, value }
        else next.push({ t: now, value })
        return next.slice(-MAX_POINTS)
      }
      this.tempHistory = append(this.tempHistory, Math.round(tempValue * 10) / 10)
      this.powerHistory = append(this.powerHistory, Math.round(powerValue))
      saveHistory(this.tempHistory, this.powerHistory)
    },
    connectEvents() {
      if (typeof EventSource === 'undefined') return
      if (eventSource) eventSource.close()
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      const ui = useUiStore()
      eventSource = new EventSource(`${API_BASE}/system/events`)
      eventSource.onopen = () => {
        this.connected = true
        this.error = null
        reconnectAttempts = 0
      }
      const handleSnapshot = (event: MessageEvent) => {
        try {
          const payload = JSON.parse(event.data)
          const snapshot = payload.data ?? payload
          this.applySnapshot(snapshot as Snapshot)
          this.connected = true
        } catch {
          // ignore malformed events
        }
      }
      eventSource.addEventListener('snapshot', handleSnapshot as EventListener)
      eventSource.addEventListener('state', handleSnapshot as EventListener)
      eventSource.addEventListener(
        'device_update',
        ((event: MessageEvent) => {
          try {
            const payload = JSON.parse(event.data)
            const device = payload.data?.device ?? payload.device
            if (device) this.upsertDevice(device as Device)
          } catch {
            // ignore
          }
        }) as EventListener,
      )
      eventSource.addEventListener(
        'notification',
        ((event: MessageEvent) => {
          try {
            const payload = JSON.parse(event.data)
            const data = payload.data ?? payload
            if (data?.message) ui.notify(data.level || 'info', data.message)
          } catch {
            // ignore
          }
        }) as EventListener,
      )
      eventSource.onerror = () => {
        this.connected = false
        eventSource?.close()
        eventSource = null
        this.scheduleReconnect()
      }
    },
    scheduleReconnect() {
      if (reconnectTimer) return
      const delay = Math.min(15000, 1200 * Math.pow(1.6, reconnectAttempts))
      reconnectAttempts += 1
      reconnectTimer = window.setTimeout(async () => {
        reconnectTimer = null
        if (!this.ready) {
          try {
            const snapshot = await api.get<Snapshot>('/devices')
            this.applySnapshot(snapshot)
          } catch {
            this.scheduleReconnect()
            return
          }
        }
        this.connectEvents()
      }, delay)
    },
    disconnectEvents() {
      eventSource?.close()
      eventSource = null
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      if (statusTimer) {
        window.clearInterval(statusTimer)
        statusTimer = null
      }
      this.connected = false
    },
    startStatusPolling() {
      if (statusTimer) return
      statusTimer = window.setInterval(() => {
        this.refreshStatus().catch(() => undefined)
      }, 30000)
    },
    async refreshStatus() {
      try {
        this.status = await api.get<SystemStatus>('/system/status')
      } catch {
        // connection badge handles failures
      }
    },
    upsertDevice(device: Device) {
      const index = this.devices.findIndex((item) => item.id === device.id)
      if (index >= 0) this.devices.splice(index, 1, device)
      else this.devices.push(device)
      this.devices.sort((a, b) => a.sort_order - b.sort_order)
      this.lastUpdated = new Date().toISOString()
    },
    selectDevice(deviceId: string | null) {
      this.selectedDeviceId = deviceId
    },
    async controlDevice(
      deviceId: string,
      properties: Record<string, any>,
      options: { quiet?: boolean } = {},
    ): Promise<Device | null> {
      const ui = useUiStore()
      try {
        const response = await api.patch<{ ok: boolean; device: Device }>(
          `/devices/${deviceId}`,
          { properties },
        )
        this.upsertDevice(response.device)
        if (!options.quiet) {
          ui.success(`${response.device.name} 已更新`)
        }
        return response.device
      } catch (error) {
        ui.toastFromError(error, '设备控制失败')
        return null
      }
    },
    async setConnectivity(deviceId: string, online: boolean) {
      const ui = useUiStore()
      try {
        const response = await api.post<{ ok: boolean; device: Device }>(
          `/devices/${deviceId}/connectivity`,
          { online },
        )
        this.upsertDevice(response.device)
        ui.notify(
          online ? 'success' : 'warning',
          online ? `${response.device.name} 已恢复在线` : `${response.device.name} 已模拟离线`,
        )
        return response.device
      } catch (error) {
        ui.toastFromError(error, '连接状态切换失败')
        return null
      }
    },
    async resetDevices() {
      const ui = useUiStore()
      try {
        await api.post('/system/reset-devices')
        const snapshot = await api.get<Snapshot>('/devices')
        this.applySnapshot(snapshot)
        ui.success('设备已恢复到演示初始状态')
      } catch (error) {
        ui.toastFromError(error, '重置失败')
      }
    },
    async refreshSnapshot() {
      try {
        const snapshot = await api.get<Snapshot>('/devices')
        this.applySnapshot(snapshot)
      } catch {
        // ignore
      }
    },
  },
})
