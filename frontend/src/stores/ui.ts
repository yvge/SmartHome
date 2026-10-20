import { defineStore } from 'pinia'
import type { ToastItem } from '@/types'
import { uid } from '@/utils/format'

let toastSeed = 0
let confirmResolver: ((value: boolean) => void) | null = null

export const useUiStore = defineStore('ui', {
  state: () => ({
    toasts: [] as ToastItem[],
    confirmDialog: null as { title: string; message: string; danger: boolean } | null,
    mobileNavOpen: false,
  }),
  actions: {
    notify(level: ToastItem['level'], message: string, duration = 3200) {
      const toast: ToastItem = { id: ++toastSeed, level, message }
      this.toasts.push(toast)
      window.setTimeout(() => this.dismiss(toast.id), duration)
    },
    success(message: string) {
      this.notify('success', message)
    },
    error(message: string) {
      this.notify('error', message, 4200)
    },
    warning(message: string) {
      this.notify('warning', message, 3800)
    },
    info(message: string) {
      this.notify('info', message)
    },
    dismiss(id: number) {
      this.toasts = this.toasts.filter((toast) => toast.id !== id)
    },
    askConfirm(message: string, title = '确认操作', danger = false): Promise<boolean> {
      this.confirmDialog = { title, message, danger }
      return new Promise((resolve) => {
        confirmResolver = resolve
      })
    },
    answerConfirm(value: boolean) {
      this.confirmDialog = null
      confirmResolver?.(value)
      confirmResolver = null
    },
    toastFromError(error: unknown, fallback = '操作失败') {
      const message = error instanceof Error ? error.message : fallback
      this.error(message || fallback)
    },
    toggleMobileNav(force?: boolean) {
      this.mobileNavOpen = force ?? !this.mobileNavOpen
    },
  },
})

export function randomId(prefix = ''): string {
  return uid(prefix)
}
