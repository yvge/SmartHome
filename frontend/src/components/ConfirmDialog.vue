<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { AlertTriangle, X } from 'lucide-vue-next'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()

function onKeydown(event: KeyboardEvent) {
  if (!ui.confirmDialog) return
  if (event.key === 'Escape') ui.answerConfirm(false)
  if (event.key === 'Enter') ui.answerConfirm(true)
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="ui.confirmDialog" class="dialog-backdrop" @click.self="ui.answerConfirm(false)">
        <div class="dialog" role="dialog" aria-modal="true">
          <div class="dialog-head">
            <div class="dialog-icon" :class="{ danger: ui.confirmDialog.danger }">
              <AlertTriangle :size="18" />
            </div>
            <button class="icon-btn sm" aria-label="关闭" @click="ui.answerConfirm(false)">
              <X :size="14" />
            </button>
          </div>
          <h3 class="dialog-title">{{ ui.confirmDialog.title }}</h3>
          <p class="dialog-message">{{ ui.confirmDialog.message }}</p>
          <div class="dialog-actions">
            <button class="btn btn-sm" @click="ui.answerConfirm(false)">取消</button>
            <button
              class="btn btn-sm"
              :class="ui.confirmDialog.danger ? 'btn-danger' : 'btn-primary'"
              @click="ui.answerConfirm(true)"
            >
              确认
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 400;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(33, 29, 25, 0.36);
  backdrop-filter: blur(8px);
}

.dialog {
  width: min(400px, 100%);
  border: 1px solid var(--line-strong);
  border-radius: 18px;
  background: var(--panel-solid);
  box-shadow: var(--shadow-lg);
  padding: 20px;
}

.dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.dialog-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  color: var(--warning);
  background: var(--amber-soft);
  border: 1px solid rgba(169, 105, 28, 0.18);
}

.dialog-icon.danger {
  color: var(--critical);
  background: var(--critical-soft);
  border-color: rgba(168, 58, 50, 0.2);
}

.dialog-title {
  font-size: 17px;
  margin-bottom: 7px;
}

.dialog-message {
  color: var(--text-2);
  font-size: 12.5px;
  line-height: 1.6;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
</style>
