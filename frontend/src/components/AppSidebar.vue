<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import {
  Activity,
  Cpu,
  Database,
  LayoutDashboard,
  Sparkles,
  Workflow,
  Zap,
} from 'lucide-vue-next'
import { useHomeStore } from '@/stores/home'
import { useChatStore } from '@/stores/chat'

const route = useRoute()
const home = useHomeStore()
const chat = useChatStore()

const navItems = [
  { path: '/', label: '总览', icon: LayoutDashboard },
  { path: '/chat', label: 'AI 管家', icon: Sparkles },
  { path: '/devices', label: '设备', icon: Cpu },
  { path: '/scenes', label: '场景编排', icon: Workflow },
  { path: '/knowledge', label: '知识库', icon: Database },
  { path: '/executions', label: '运行轨迹', icon: Activity },
]

const isActive = (path: string) => route.path === path

const badgeFor = (path: string): string | null => {
  if (path === '/devices' && home.onlineDevices.length) return String(home.onlineDevices.length)
  if (path === '/chat' && chat.streaming) return 'AI'
  return null
}

const modeText = computed(() => {
  if (!home.status) return '连接中'
  return home.status.llm.enabled ? 'LLM 在线' : '离线规则'
})

const modelText = computed(() => {
  if (!home.status) return '—'
  return home.status.llm.enabled ? home.status.llm.model : 'rule-engine'
})

const ragText = computed(() => home.ragLabel)
const version = computed(() => home.status?.app.version || '1.0.0')
</script>

<template>
  <aside class="sidebar">
    <RouterLink to="/" class="brand">
      <div class="brand-mark">
        <svg width="21" height="21" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M4 11.2 12 4l8 7.2V19a1.8 1.8 0 0 1-1.8 1.8H5.8A1.8 1.8 0 0 1 4 19v-7.8Z"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linejoin="round"
          />
          <circle cx="12" cy="14" r="2.6" fill="currentColor" />
          <path d="M12 5.8v1.8M8.5 8.6l1.1 1.1M15.5 8.6l-1.1 1.1" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
        </svg>
      </div>
      <div class="brand-text">
        <div class="brand-name">智慧居</div>
        <div class="brand-sub">Agent Platform</div>
      </div>
    </RouterLink>

    <nav class="nav" aria-label="主导航">
      <div class="nav-section-label">控制中心</div>
      <RouterLink
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
      >
        <component :is="item.icon" :size="18" :stroke-width="1.8" class="nav-icon" />
        <span class="nav-label">{{ item.label }}</span>
        <span v-if="badgeFor(item.path)" class="nav-badge">{{ badgeFor(item.path) }}</span>
      </RouterLink>
    </nav>

    <div class="sidebar-spacer"></div>

    <div class="runtime-card">
      <div class="runtime-head">
        <div class="runtime-title">AI Runtime</div>
        <span class="runtime-live"><i></i>{{ home.connected ? 'LIVE' : 'SYNC' }}</span>
      </div>
      <div class="runtime-row">
        <span>推理模式</span>
        <strong :class="{ 'mint-text': home.status?.llm.enabled }">{{ modeText }}</strong>
      </div>
      <div class="runtime-row">
        <span>模型</span>
        <strong class="mono">{{ modelText }}</strong>
      </div>
      <div class="runtime-row">
        <span>向量检索</span>
        <strong>{{ ragText }}</strong>
      </div>
      <div class="runtime-row">
        <span>设备在线</span>
        <strong>{{ home.onlineDevices.length }} / {{ home.devices.length }}</strong>
      </div>
      <div class="runtime-foot">
        <span>v{{ version }}</span>
        <span>2024.12</span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.runtime-live {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: 8.5px;
  letter-spacing: 0.12em;
  color: var(--mint);
}

.runtime-live i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--mint);
  box-shadow: 0 0 8px rgba(94, 234, 212, 0.8);
  animation: pulse-soft 2.2s ease infinite;
}

.mint-text {
  color: var(--mint) !important;
}

@media (max-width: 1240px) {
  .runtime-card {
    display: none;
  }
}
</style>
