<script setup lang="ts">
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-vue-next'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const icons = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}
</script>

<template>
  <Teleport to="body">
    <div class="toast-stack" aria-live="polite">
      <TransitionGroup name="toast">
        <div
          v-for="toast in ui.toasts"
          :key="toast.id"
          class="toast"
          :class="toast.level"
          role="status"
        >
          <component :is="icons[toast.level]" :size="16" class="toast-icon" />
          <span class="toast-text">{{ toast.message }}</span>
          <button class="toast-close" aria-label="关闭提示" @click="ui.dismiss(toast.id)">
            <X :size="13" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  top: 18px;
  right: 22px;
  z-index: 300;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(360px, calc(100vw - 40px));
  pointer-events: none;
}

.toast {
  pointer-events: auto;
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 11px 12px;
  border-radius: 12px;
  border: 1px solid var(--line-strong);
  background: rgba(255, 253, 249, 0.98);
  backdrop-filter: blur(18px);
  box-shadow: 0 16px 40px rgba(60, 45, 30, 0.12);
  font-size: 12px;
  color: var(--text);
}

.toast.success {
  border-color: rgba(61, 122, 82, 0.25);
}

.toast.error {
  border-color: rgba(168, 58, 50, 0.25);
}

.toast.warning {
  border-color: rgba(169, 105, 28, 0.25);
}

.toast-icon {
  flex: 0 0 auto;
  margin-top: 1px;
}

.toast.success .toast-icon {
  color: var(--good);
}

.toast.error .toast-icon {
  color: var(--critical);
}

.toast.warning .toast-icon {
  color: var(--warning);
}

.toast.info .toast-icon {
  color: var(--indigo);
}

.toast-text {
  flex: 1;
  line-height: 1.5;
}

.toast-close {
  border: none;
  background: transparent;
  color: var(--text-4);
  padding: 1px;
  display: grid;
  place-items: center;
}

.toast-close:hover {
  color: var(--text);
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(14px);
}

@media (max-width: 760px) {
  .toast-stack {
    top: 10px;
    right: 12px;
    width: calc(100vw - 24px);
  }
}
</style>
