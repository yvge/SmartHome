<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Database, Sparkles, Wifi, WifiOff } from 'lucide-vue-next'
import { useHomeStore } from '@/stores/home'
import { pad } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const home = useHomeStore()

const now = ref(new Date())
let timer: number | undefined

onMounted(() => {
  timer = window.setInterval(() => {
    now.value = new Date()
  }, 1000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})

const title = computed(() => (route.meta.title as string) || '智慧居')
const subtitle = computed(() => (route.meta.subtitle as string) || '')
const clock = computed(() => `${pad(now.value.getHours())}:${pad(now.value.getMinutes())}`)
const dateText = computed(() => {
  const week = ['日', '一', '二', '三', '四', '五', '六'][now.value.getDay()]
  return `${now.value.getMonth() + 1}月${now.value.getDate()}日 周${week}`
})

const llmLabel = computed(() => {
  if (!home.status) return '模型连接中'
  return home.status.llm.enabled ? home.status.llm.model : '离线规则引擎'
})
const ragLabel = computed(() => home.ragLabel)

function openChat() {
  if (route.path !== '/chat') router.push('/chat')
}
</script>

<template>
  <header class="topbar">
    <div class="topbar-titles">
      <div class="topbar-title">{{ title }}</div>
      <div class="topbar-sub">{{ subtitle }}</div>
    </div>

    <div class="topbar-actions">
      <div class="clock">
        <div class="clock-time">{{ clock }}</div>
        <div class="clock-date">{{ dateText }}</div>
      </div>

      <div class="status-pill" :class="home.connected ? 'online' : 'warn'">
        <span class="dot"></span>
        <Wifi v-if="home.connected" :size="12" />
        <WifiOff v-else :size="12" />
        <span class="hide-sm">{{ home.connected ? '实时连接' : '重连中' }}</span>
      </div>

      <div class="status-pill hide-md" :class="{ online: home.status?.llm.enabled }">
        <span class="dot"></span>
        <Sparkles :size="12" />
        <span class="hide-sm">{{ llmLabel }}</span>
      </div>

      <div class="status-pill hide-md">
        <span class="dot" :class="{ 'dot-mint': home.status?.rag.healthy }"></span>
        <Database :size="12" />
        <span>{{ ragLabel }}</span>
      </div>

      <button
        v-if="route.path !== '/chat'"
        class="icon-btn hide-sm"
        title="打开 AI 管家"
        @click="openChat"
      >
        <Sparkles :size="17" />
      </button>

      <div class="avatar" title="家庭管理员">居</div>
    </div>
  </header>
</template>

<style scoped>
.dot-mint {
  background: var(--mint) !important;
  box-shadow: 0 0 8px rgba(94, 234, 212, 0.6);
}
</style>
