<script setup lang="ts">
import { computed } from 'vue'
import type { Device, RoomClimate, RoomMeta } from '@/types'
import { acModeLabel, devicePrimaryMetric } from '@/utils/format'
import DeviceIcon from '@/components/DeviceIcon.vue'

const props = defineProps<{
  devices: Device[]
  rooms: RoomClimate[]
  roomMeta: RoomMeta[]
  period?: string
  selectedId?: string | null
}>()

const emit = defineEmits<{ (event: 'select', device: Device): void }>()

const ROOM_BOXES: Record<string, { label: string; className: string }> = {
  bedroom: { label: '主卧', className: 'room-bedroom' },
  study: { label: '书房', className: 'room-study' },
  second_bedroom: { label: '次卧', className: 'room-second' },
  living: { label: '客厅', className: 'room-living' },
  kitchen: { label: '厨房', className: 'room-kitchen' },
  balcony: { label: '阳台', className: 'room-balcony' },
}

const POSITIONS: Record<string, { x: number; y: number }> = {
  curtain_bed: { x: 7.5, y: 25 },
  light_bed_main: { x: 21, y: 24 },
  ac_bed: { x: 28.5, y: 33 },
  light_bed_bedside: { x: 13.5, y: 36 },
  humidifier_bed: { x: 26.5, y: 40 },
  light_study: { x: 48, y: 23 },
  light_second: { x: 76, y: 24 },
  sensor_second: { x: 86, y: 32 },
  curtain_living: { x: 7.5, y: 61 },
  light_living_main: { x: 20, y: 67 },
  light_living_strip: { x: 33, y: 60 },
  ac_living: { x: 58, y: 61.5 },
  sensor_living: { x: 12, y: 75 },
  purifier_living: { x: 24, y: 80 },
  socket_tv: { x: 48, y: 84 },
  speaker_living: { x: 60, y: 80 },
  vacuum_robot: { x: 38, y: 89 },
  light_kitchen: { x: 84, y: 61 },
  light_balcony: { x: 84, y: 87 },
  curtain_balcony: { x: 74, y: 82 },
}

const roomMap = computed(() => {
  const map: Record<string, RoomMeta> = {}
  for (const room of props.roomMeta) map[room.id] = room
  return map
})

const climateMap = computed(() => {
  const map: Record<string, RoomClimate> = {}
  for (const room of props.rooms) map[room.id] = room
  return map
})

const devicesByRoom = computed(() => {
  const map: Record<string, Device[]> = {}
  for (const device of props.devices) {
    if (!map[device.room_id]) map[device.room_id] = []
    map[device.room_id].push(device)
  }
  return map
})

const night = computed(() => ['傍晚', '夜晚', '深夜'].includes(props.period || ''))

function positionFor(device: Device) {
  return POSITIONS[device.id] || { x: 50, y: 50 }
}

function isActive(device: Device): boolean {
  const p = device.properties
  if (!device.online) return false
  switch (device.type) {
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
}

function markerStyle(device: Device) {
  const position = positionFor(device)
  const p = device.properties
  const glow =
    device.type === 'light' && p.power
      ? `${p.color_hex || '#f8c66a'}88`
      : isActive(device)
        ? 'rgba(94,234,212,.32)'
        : 'transparent'
  return {
    left: `${position.x}%`,
    top: `${position.y}%`,
    '--marker-glow': glow,
    '--marker-color':
      device.type === 'light' && p.power
        ? p.color_hex || '#f8c66a'
        : isActive(device)
          ? '#5eead4'
          : '#8ea2b8',
  }
}

function roomClimate(roomId: string) {
  return climateMap.value[roomId]
}

function roomLabel(roomId: string) {
  return roomMap.value[roomId]?.name || ROOM_BOXES[roomId]?.label || roomId
}

function roomDevices(roomId: string) {
  return devicesByRoom.value[roomId] || []
}

function markerTitle(device: Device): string {
  return `${device.name}：${devicePrimaryMetric(device)}`
}

defineExpose({ markerTitle })
</script>

<template>
  <div class="floorplan" :class="{ night }">
    <div class="floor-grid"></div>

    <div
      v-for="(box, roomId) in ROOM_BOXES"
      :key="roomId"
      class="room"
      :class="box.className"
    >
      <div class="room-head">
        <span class="room-name">{{ roomLabel(roomId) }}</span>
        <span v-if="roomClimate(roomId)" class="room-climate mono">
          {{ roomClimate(roomId)!.temperature }}° · {{ roomClimate(roomId)!.humidity }}%
        </span>
        <span v-else class="room-climate empty">待接入</span>
      </div>

      <div v-if="roomId === 'living'" class="furniture sofa"></div>
      <div v-if="roomId === 'living'" class="furniture table"></div>
      <div v-if="roomId === 'living'" class="furniture tv"></div>
      <div v-if="roomId === 'bedroom'" class="furniture bed"></div>
      <div v-if="roomId === 'bedroom'" class="furniture nightstand"></div>
      <div v-if="roomId === 'study'" class="furniture desk"></div>
      <div v-if="roomId === 'study'" class="furniture chair"></div>
      <div v-if="roomId === 'kitchen'" class="furniture counter"></div>
      <div v-if="roomId === 'balcony'" class="furniture plant one"></div>
      <div v-if="roomId === 'balcony'" class="furniture plant two"></div>

      <div class="room-device-count">
        <span>{{ roomDevices(roomId).length }}</span> 设备
      </div>
    </div>

    <button
      v-for="device in devices"
      :key="device.id"
      class="device-marker"
      :class="{
        active: isActive(device),
        offline: !device.online,
        selected: selectedId === device.id,
        sensor: device.type === 'sensor',
      }"
      :style="markerStyle(device)"
      :title="markerTitle(device)"
      :aria-label="`${device.name}，${devicePrimaryMetric(device)}`"
      @click.stop="emit('select', device)"
    >
      <span class="marker-halo"></span>
      <DeviceIcon :icon="device.icon" :size="15" :stroke-width="1.9" />
      <span class="marker-label">
        <strong>{{ device.name }}</strong>
        <em>{{ devicePrimaryMetric(device) }}</em>
      </span>
    </button>

    <div class="plan-compass" aria-hidden="true">
      <span>N</span>
      <i></i>
    </div>
    <div class="plan-legend">
      <span><i class="lg-on"></i>运行中</span>
      <span><i class="lg-off"></i>待机</span>
      <span><i class="lg-offline"></i>离线</span>
    </div>
  </div>
</template>

<style scoped>
.floorplan {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9.4;
  min-height: 330px;
  border-radius: 16px;
  overflow: hidden;
  background:
    radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.02), transparent 40%),
    linear-gradient(145deg, rgba(16, 27, 39, 0.88), rgba(8, 14, 21, 0.94));
  border: 1px solid rgba(148, 178, 209, 0.09);
  transition: background 0.6s ease;
}

.floorplan.night {
  background:
    radial-gradient(circle at 25% 25%, rgba(139, 149, 248, 0.05), transparent 42%),
    linear-gradient(145deg, rgba(11, 18, 30, 0.94), rgba(5, 9, 15, 0.98));
}

.floor-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(148, 178, 209, 0.038) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 178, 209, 0.038) 1px, transparent 1px);
  background-size: 26px 26px;
  mask-image: radial-gradient(ellipse at 50% 45%, black 30%, transparent 82%);
  pointer-events: none;
}

.room {
  position: absolute;
  border-radius: 13px;
  border: 1px solid rgba(148, 178, 209, 0.12);
  background:
    linear-gradient(160deg, rgba(255, 255, 255, 0.022), rgba(255, 255, 255, 0.005));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.035);
  overflow: hidden;
}

.room::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(148, 178, 209, 0.025) 1px, transparent 1px);
  background-size: 100% 14px;
  opacity: 0.5;
  pointer-events: none;
}

.room-bedroom {
  left: 3%;
  top: 4%;
  width: 31%;
  height: 40%;
}

.room-study {
  left: 36%;
  top: 4%;
  width: 22%;
  height: 40%;
}

.room-second {
  left: 60%;
  top: 4%;
  width: 37%;
  height: 40%;
}

.room-living {
  left: 3%;
  top: 47%;
  width: 65%;
  height: 49%;
}

.room-kitchen {
  left: 70%;
  top: 47%;
  width: 27%;
  height: 23%;
}

.room-balcony {
  left: 70%;
  top: 72%;
  width: 27%;
  height: 24%;
}

.room-head {
  position: absolute;
  top: 9px;
  left: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  z-index: 2;
  pointer-events: none;
}

.room-name {
  font-size: 10px;
  font-weight: 550;
  letter-spacing: 0.12em;
  color: rgba(214, 230, 244, 0.62);
}

.room-climate {
  font-size: 9px;
  color: var(--text-4);
  white-space: nowrap;
}

.room-climate.empty {
  color: rgba(100, 118, 140, 0.5);
  font-style: italic;
}

.room-device-count {
  position: absolute;
  right: 10px;
  bottom: 8px;
  font-size: 8.5px;
  color: var(--text-4);
  z-index: 2;
  pointer-events: none;
}

.room-device-count span {
  color: var(--text-3);
  font-variant-numeric: tabular-nums;
}

/* furniture sketches */
.furniture {
  position: absolute;
  border: 1px solid rgba(148, 178, 209, 0.08);
  background: rgba(148, 178, 209, 0.035);
  border-radius: 6px;
  pointer-events: none;
}

.sofa {
  left: 10%;
  top: 64%;
  width: 28%;
  height: 12%;
  border-radius: 8px 8px 4px 4px;
}

.table {
  left: 19%;
  top: 80%;
  width: 13%;
  height: 7%;
  border-radius: 50%;
}

.tv {
  right: 12%;
  top: 55%;
  width: 2px;
  height: 22%;
  background: rgba(148, 178, 209, 0.13);
  border: none;
}

.bed {
  left: 8%;
  top: 22%;
  width: 17%;
  height: 8%;
  border-radius: 5px;
  background: rgba(139, 149, 248, 0.045);
  border-color: rgba(139, 149, 248, 0.09);
}

.nightstand {
  right: 12%;
  top: 20%;
  width: 6%;
  height: 6%;
}

.desk {
  left: 12%;
  top: 66%;
  width: 70%;
  height: 8%;
}

.chair {
  left: 40%;
  top: 58%;
  width: 12%;
  height: 7%;
  border-radius: 50%;
}

.counter {
  left: 8%;
  top: 48%;
  width: 70%;
  height: 7%;
}

.plant {
  width: 10%;
  height: 16%;
  border-radius: 50% 50% 40% 40%;
  border-color: rgba(85, 217, 154, 0.12);
  background: rgba(85, 217, 154, 0.04);
}

.plant.one {
  left: 16%;
  top: 32%;
}

.plant.two {
  right: 18%;
  top: 45%;
  width: 7%;
  height: 12%;
}

/* markers */
.device-marker {
  position: absolute;
  z-index: 5;
  transform: translate(-50%, -50%);
  width: 30px;
  height: 30px;
  border-radius: 10px;
  border: 1px solid rgba(148, 178, 209, 0.18);
  background: rgba(11, 19, 28, 0.9);
  color: var(--marker-color, var(--text-2));
  display: grid;
  place-items: center;
  transition:
    transform 0.18s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
  padding: 0;
}

.device-marker:hover,
.device-marker:focus-visible {
  transform: translate(-50%, -50%) scale(1.16);
  border-color: rgba(255, 255, 255, 0.3);
  z-index: 12;
  outline: none;
}

.device-marker.active {
  border-color: color-mix(in srgb, var(--marker-color) 45%, transparent);
  box-shadow:
    0 0 22px var(--marker-glow),
    inset 0 0 14px color-mix(in srgb, var(--marker-color) 12%, transparent);
}

.device-marker.selected {
  transform: translate(-50%, -50%) scale(1.16);
  border-color: rgba(255, 255, 255, 0.5);
  z-index: 13;
}

.device-marker.offline {
  opacity: 0.48;
  border-style: dashed;
}

.device-marker.sensor {
  border-radius: 50%;
}

.marker-halo {
  position: absolute;
  inset: -5px;
  border-radius: inherit;
  background: var(--marker-glow);
  filter: blur(9px);
  opacity: 0.6;
  z-index: -1;
  pointer-events: none;
}

.marker-label {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%) translateY(4px);
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 6px 8px;
  border-radius: 7px;
  background: rgba(7, 13, 20, 0.94);
  border: 1px solid var(--line-strong);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35);
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.device-marker:hover .marker-label,
.device-marker:focus-visible .marker-label,
.device-marker.selected .marker-label {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.marker-label strong {
  font-size: 10px;
  font-weight: 550;
  color: var(--text);
}

.marker-label em {
  font-style: normal;
  font-size: 9px;
  color: var(--text-3);
  font-variant-numeric: tabular-nums;
}

.plan-compass {
  position: absolute;
  top: 12px;
  right: 14px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid var(--line);
  display: grid;
  place-items: center;
  font-family: var(--font-mono);
  font-size: 8px;
  color: var(--text-4);
  pointer-events: none;
}

.plan-compass i {
  position: absolute;
  top: 4px;
  left: 50%;
  width: 1px;
  height: 6px;
  background: var(--mint);
  transform: translateX(-50%);
}

.plan-legend {
  position: absolute;
  left: 14px;
  bottom: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 8.5px;
  color: var(--text-4);
  pointer-events: none;
}

.plan-legend span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.plan-legend i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
}

.lg-on {
  background: var(--mint);
  box-shadow: 0 0 6px rgba(94, 234, 212, 0.7);
}

.lg-off {
  background: var(--text-4);
}

.lg-offline {
  border: 1px solid var(--critical);
  background: transparent;
}

@media (max-width: 760px) {
  .floorplan {
    min-height: 280px;
    aspect-ratio: 4 / 3.4;
  }

  .device-marker {
    width: 26px;
    height: 26px;
    border-radius: 8px;
  }

  .room-device-count,
  .plan-legend {
    display: none;
  }
}
</style>
