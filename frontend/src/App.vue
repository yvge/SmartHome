<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { RouterView } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import AppTopbar from '@/components/AppTopbar.vue'
import ToastStack from '@/components/ToastStack.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import SceneRunnerOverlay from '@/components/SceneRunnerOverlay.vue'
import DeviceDrawer from '@/components/DeviceDrawer.vue'
import { useHomeStore } from '@/stores/home'
import { useSceneStore } from '@/stores/scenes'
import { useChatStore } from '@/stores/chat'

const home = useHomeStore()
const scenes = useSceneStore()
const chat = useChatStore()

onMounted(async () => {
  await home.bootstrap()
  await scenes.fetchScenes()
  await chat.initialize()
})

onBeforeUnmount(() => {
  home.disconnectEvents()
})
</script>

<template>
  <div class="app-shell">
    <AppSidebar />
    <div class="main-col">
      <AppTopbar />
      <Transition name="fade">
        <div v-if="home.ready && !home.connected" class="conn-banner">
          <span class="conn-dot"></span>
          实时状态连接中断，正在重连… 设备控制仍可通过 AI 管家执行
        </div>
      </Transition>
      <main class="main-scroll">
        <RouterView v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <component :is="Component" :key="$route.path" />
          </Transition>
        </RouterView>
      </main>
    </div>
    <ToastStack />
    <ConfirmDialog />
    <SceneRunnerOverlay />
    <DeviceDrawer />
  </div>
</template>

<style scoped>
.conn-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 34px;
  font-size: 11.5px;
  color: var(--warning);
  background: rgba(169, 105, 28, 0.06);
  border-bottom: 1px solid rgba(169, 105, 28, 0.12);
}

.conn-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--warning);
  animation: pulse-soft 1.6s ease infinite;
}

@media (max-width: 760px) {
  .conn-banner {
    padding: 6px 16px;
    font-size: 10.5px;
  }
}
</style>
