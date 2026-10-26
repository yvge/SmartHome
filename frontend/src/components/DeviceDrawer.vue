<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ArrowDownToLine, ArrowUpFromLine, Check, Loader2, WifiOff, X } from 'lucide-vue-next'
import DeviceIcon from '@/components/DeviceIcon.vue'
import DeviceControls from '@/components/DeviceControls.vue'
import { useHomeStore } from '@/stores/home'
import { formatTime } from '@/utils/format'

const home = useHomeStore()
const device = computed(() => home.selectedDevice)
const saving = ref(false)
const lastSynced = ref<string>('')
const lastSavedAt = ref<number>(0)

const glow = computed(() => {
  if (!device.value) return 'transparent'
  if (!device.value.online) return 'rgba(41, 37, 36, 0.08)'
  const p = device.value.properties
  if (device.value.type === 'light' && p.power) return `${p.color_hex || '#c08a3e'}66`
  if (device.value.type === 'sensor') return 'rgba(180, 74, 38, 0.2)'
  if (p.power || p.playing) return 'rgba(180, 74, 38, 0.2)'
  return 'rgba(41, 37, 36, 0.12)'
})

const iconColor = computed(() => {
  if (!device.value) return 'var(--text-2)'
  if (!device.value.online) return 'var(--text-4)'
  const p = device.value.properties
  if (device.value.type === 'light' && p.power) return p.color_hex || 'var(--amber)'
  if (p.power || p.playing) return 'var(--mint)'
  return 'var(--text-2)'
})

watch(
  () => device.value?.id,
  () => {
    lastSynced.value = ''
    saving.value = false
  },
)

watch(
  () => device.value?.updated_at,
  (value) => {
    if (value) lastSavedAt.value = new Date(value).getTime()
  },
)

async function applyPatch(patch: Record<string, any>) {
  if (!device.value) return
  saving.value = true
  const result = await home.controlDevice(device.value.id, patch, { quiet: true })
  saving.value = false
  if (result) {
    lastSynced.value = `已同步 ${formatTime(result.updated_at)}`
    lastSavedAt.value = Date.now()
  }
}

async function toggleOnline() {
  if (!device.value) return
  await home.setConnectivity(device.value.id, !device.value.online)
}

function close() {
  home.selectDevice(null)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && device.value) close()
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="device" class="drawer-backdrop" @click.self="close">
        <aside class="device-drawer" role="dialog" aria-modal="true" :aria-label="`${device.name} 控制面板`">
          <header class="drawer-head">
            <div class="drawer-device">
              <div
                class="drawer-icon"
                :style="{
                  color: iconColor,
                  borderColor: glow,
                  boxShadow: `0 0 36px ${glow}`,
                }"
              >
                <DeviceIcon :icon="device.icon" :size="25" />
              </div>
              <div>
                <div class="drawer-title">{{ device.name }}</div>
                <div class="drawer-meta">
                  {{ device.room }} · {{ device.type_label }}
                  <span class="meta-dot">·</span>
                  <span :class="device.online ? 'online-text' : 'offline-text'">
                    {{ device.online ? '在线' : '离线' }}
                  </span>
                </div>
              </div>
            </div>
            <button class="icon-btn sm" aria-label="关闭" @click="close">
              <X :size="15" />
            </button>
          </header>

          <div class="drawer-statusline">
            <span class="chip" :class="device.online ? 'mint' : 'rose'">
              <span class="chip-dot"></span>
              {{ device.online ? '设备在线' : '设备离线' }}
            </span>
            <span v-if="saving" class="sync-state"><Loader2 :size="11" class="spin" /> 指令下发中…</span>
            <span v-else-if="lastSynced" class="sync-state synced"><Check :size="11" /> {{ lastSynced }}</span>
            <span v-else class="sync-state mono">{{ device.id }}</span>
          </div>

          <div class="drawer-body">
            <section class="drawer-section">
              <div class="section-head">
                <span class="section-label">设备控制</span>
                <span class="section-note">{{ device.capabilities.filter((c) => c.type !== 'readonly').length }} 项可写能力</span>
              </div>
              <DeviceControls :device="device" @change="applyPatch" />
            </section>

            <section class="drawer-section">
              <div class="section-head">
                <span class="section-label">接入信息</span>
                <span class="section-note">JSON Schema Tool</span>
              </div>
              <dl class="info-grid">
                <div><dt>设备 ID</dt><dd class="mono">{{ device.id }}</dd></div>
                <div><dt>设备类型</dt><dd>{{ device.type }} / {{ device.type_label }}</dd></div>
                <div><dt>所在房间</dt><dd>{{ device.room }}</dd></div>
                <div><dt>最近更新</dt><dd class="mono">{{ formatTime(lastSavedAt || device.updated_at) }}</dd></div>
              </dl>
            </section>

            <button class="connectivity-btn" :class="{ offline: !device.online }" @click="toggleOnline">
              <WifiOff v-if="device.online" :size="15" />
              <ArrowUpFromLine v-else :size="15" />
              <span>{{ device.online ? '模拟设备离线（演示异常兜底）' : '恢复设备在线' }}</span>
            </button>
            <div class="drawer-hint">
              场景执行或语音指令遇到离线设备时会触发兜底分支，可在「场景编排」中观察。
            </div>
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 350;
  background: rgba(33, 29, 25, 0.3);
  backdrop-filter: blur(6px);
  display: flex;
  justify-content: flex-end;
}

.device-drawer {
  width: min(430px, 100vw);
  height: 100%;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at 90% 0%, rgba(180, 74, 38, 0.06), transparent 45%),
    #f7f2ea;
  border-left: 1px solid var(--line-strong);
  box-shadow: -30px 0 80px rgba(60, 45, 30, 0.12);
}

.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 22px 22px 15px;
}

.drawer-device {
  display: flex;
  align-items: center;
  gap: 13px;
  min-width: 0;
}

.drawer-icon {
  width: 54px;
  height: 54px;
  flex: 0 0 54px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  background: rgba(41, 37, 36, 0.03);
  transition: color 0.25s ease, box-shadow 0.25s ease;
}

.drawer-title {
  font-family: var(--font-display);
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.drawer-meta {
  font-size: 11px;
  color: var(--text-3);
  margin-top: 3px;
}

.meta-dot {
  margin: 0 4px;
  color: var(--text-4);
}

.online-text {
  color: var(--mint);
}

.offline-text {
  color: var(--critical);
}

.drawer-statusline {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 22px 16px;
  border-bottom: 1px solid var(--line);
  flex-wrap: wrap;
}

.sync-state {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 9.5px;
  color: var(--text-4);
  margin-left: auto;
  max-width: 55%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sync-state.synced {
  color: var(--mint);
}

.spin {
  animation: spin 0.9s linear infinite;
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 22px 30px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.drawer-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.section-label {
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-3);
}

.section-note {
  font-size: 9.5px;
  color: var(--text-4);
  font-family: var(--font-mono);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.info-grid > div {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(41, 37, 36, 0.02);
  min-width: 0;
}

.info-grid dt {
  font-size: 9.5px;
  color: var(--text-4);
  margin-bottom: 3px;
}

.info-grid dd {
  margin: 0;
  font-size: 11px;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.connectivity-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 13px;
  border-radius: 11px;
  border: 1px solid rgba(169, 105, 28, 0.18);
  background: rgba(169, 105, 28, 0.045);
  color: var(--warning);
  font-size: 11.5px;
  text-align: left;
  transition: background 0.18s ease, border-color 0.18s ease;
}

.connectivity-btn:hover {
  background: rgba(169, 105, 28, 0.08);
  border-color: rgba(169, 105, 28, 0.25);
}

.connectivity-btn.offline {
  color: var(--mint);
  border-color: rgba(180, 74, 38, 0.2);
  background: rgba(180, 74, 38, 0.05);
}

.drawer-hint {
  font-size: 10px;
  line-height: 1.6;
  color: var(--text-4);
  margin-top: -14px;
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.24s ease;
}

.drawer-enter-active .device-drawer,
.drawer-leave-active .device-drawer {
  transition: transform 0.28s cubic-bezier(0.22, 0.8, 0.3, 1);
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}

.drawer-enter-from .device-drawer,
.drawer-leave-to .device-drawer {
  transform: translateX(100%);
}

@media (max-width: 760px) {
  .device-drawer {
    width: 100vw;
  }
}
</style>
