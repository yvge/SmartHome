import { defineStore } from 'pinia'
import type { Scene, SceneRunState, SceneRunStep } from '@/types'
import { api, streamPost, ApiError } from '@/services/http'
import { useUiStore } from '@/stores/ui'
import { useHomeStore } from '@/stores/home'

let runController: AbortController | null = null

function emptyRun(scene: Scene): SceneRunState {
  return {
    sceneId: scene.id,
    name: scene.name,
    icon: scene.icon,
    description: scene.description,
    status: 'running',
    condition: scene.condition
      ? { passed: true, reason: '正在判断条件…', optional: scene.condition.optional }
      : null,
    steps: scene.steps.map((step, index) => ({
      index: index + 1,
      total: scene.steps.length,
      label: step.label || '设备动作',
      device_id: step.device_id,
      status: 'pending',
    })),
    fallback: null,
    message: '',
    startedAt: Date.now(),
  }
}

export const useSceneStore = defineStore('scenes', {
  state: () => ({
    scenes: [] as Scene[],
    loading: false,
    error: null as string | null,
    activeRun: null as SceneRunState | null,
    runningSceneId: null as string | null,
  }),
  getters: {
    builtinScenes(state): Scene[] {
      return state.scenes.filter((scene) => scene.builtin)
    },
    customScenes(state): Scene[] {
      return state.scenes.filter((scene) => !scene.builtin)
    },
    sceneById(state) {
      return (id: string): Scene | undefined => state.scenes.find((scene) => scene.id === id)
    },
    isRunning(state): boolean {
      return Boolean(state.runningSceneId)
    },
  },
  actions: {
    async fetchScenes() {
      this.loading = true
      try {
        const response = await api.get<{ scenes: Scene[] }>('/scenes')
        this.scenes = response.scenes
        this.error = null
      } catch (error) {
        this.error = error instanceof Error ? error.message : '场景加载失败'
      } finally {
        this.loading = false
      }
    },
    async runScene(scene: Scene) {
      if (this.runningSceneId) {
        useUiStore().warning('已有场景正在执行，请稍候')
        return
      }
      const ui = useUiStore()
      const home = useHomeStore()
      runController = new AbortController()
      this.runningSceneId = scene.id
      this.activeRun = emptyRun(scene)
      const run = this.activeRun
      try {
        await streamPost(
          `/scenes/${scene.id}/run`,
          {},
          ({ event, data }) => {
            if (!this.activeRun || this.activeRun.sceneId !== scene.id) return
            switch (event) {
              case 'scene_start':
                run.name = data.name || run.name
                run.icon = data.icon || run.icon
                run.description = data.description || run.description
                run.steps = (data.total_steps ? Array.from({ length: data.total_steps }, (_, index) => ({
                  index: index + 1,
                  total: data.total_steps,
                  label: run.steps[index]?.label || `动作 ${index + 1}`,
                  status: 'pending' as const,
                })) : run.steps)
                break
              case 'scene_condition':
                run.condition = {
                  passed: Boolean(data.passed),
                  reason: data.reason || '',
                  optional: Boolean(data.optional),
                }
                break
              case 'scene_step': {
                const index = Number(data.index) - 1
                const step: SceneRunStep = {
                  index: Number(data.index),
                  total: Number(data.total),
                  label: data.label,
                  device_id: data.device_id,
                  device_name: data.device_name,
                  status: 'running',
                }
                if (index >= 0 && index < run.steps.length) run.steps.splice(index, 1, step)
                else run.steps.push(step)
                break
              }
              case 'scene_step_result': {
                const target = run.steps.find((step) => step.index === Number(data.index))
                if (target) {
                  target.status = data.ok ? 'done' : 'failed'
                  target.message = data.message
                }
                break
              }
              case 'scene_step_skipped': {
                const target = run.steps.find((step) => step.index === Number(data.index))
                if (target) {
                  target.status = 'skipped'
                  target.message = data.reason
                }
                break
              }
              case 'scene_fallback':
                run.fallback = {
                  success: Boolean(data.success),
                  results: data.results || [],
                }
                break
              case 'scene_done':
                run.status = data.result?.status || run.status
                run.message = data.result?.message || run.message
                break
              case 'done':
                if (data.status) run.status = data.status
                run.finishedAt = Date.now()
                home.refreshSnapshot()
                if (run.status === 'success') ui.success(run.message || `${run.name} 执行完成`)
                else if (run.status === 'partial') ui.warning(run.message || `${run.name} 部分完成`)
                else if (run.status === 'skipped') ui.info(run.message || `${run.name} 已跳过`)
                else ui.error(run.message || `${run.name} 执行失败`)
                break
              case 'error':
                run.error = data.message || '场景执行异常'
                run.status = 'failed'
                break
              default:
                break
            }
          },
          runController.signal,
        )
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          run.status = 'failed'
          run.message = '执行已取消'
          return
        }
        run.status = 'failed'
        run.message = error instanceof ApiError ? error.message : error instanceof Error ? error.message : '场景执行失败'
        ui.error(run.message)
      } finally {
        this.runningSceneId = null
        runController = null
      }
    },
    stopScene() {
      runController?.abort()
    },
    closeRun() {
      if (this.activeRun) this.activeRun.finishedAt = this.activeRun.finishedAt || Date.now()
      this.activeRun = null
    },
    async createScene(payload: Record<string, unknown>): Promise<Scene | null> {
      const ui = useUiStore()
      try {
        const response = await api.post<{ scene: Scene }>('/scenes', payload)
        await this.fetchScenes()
        ui.success(`场景「${response.scene.name}」已创建`)
        return response.scene
      } catch (error) {
        ui.toastFromError(error, '创建场景失败')
        return null
      }
    },
    async updateScene(sceneId: string, payload: Record<string, unknown>): Promise<Scene | null> {
      const ui = useUiStore()
      try {
        const response = await api.put<{ scene: Scene }>(`/scenes/${sceneId}`, payload)
        await this.fetchScenes()
        ui.success(`场景「${response.scene.name}」已更新`)
        return response.scene
      } catch (error) {
        ui.toastFromError(error, '更新场景失败')
        return null
      }
    },
    async duplicateScene(sceneId: string): Promise<Scene | null> {
      const ui = useUiStore()
      try {
        const response = await api.post<{ scene: Scene }>(`/scenes/${sceneId}/duplicate`)
        await this.fetchScenes()
        ui.success(`已复制为「${response.scene.name}」`)
        return response.scene
      } catch (error) {
        ui.toastFromError(error, '复制场景失败')
        return null
      }
    },
    async deleteScene(sceneId: string): Promise<boolean> {
      const ui = useUiStore()
      const scene = this.sceneById(sceneId)
      const confirmed = await ui.askConfirm(
        `删除场景「${scene?.name || sceneId}」？该操作不可撤销。`,
        '删除场景',
        true,
      )
      if (!confirmed) return false
      try {
        await api.delete(`/scenes/${sceneId}`)
        await this.fetchScenes()
        ui.success('场景已删除')
        return true
      } catch (error) {
        ui.toastFromError(error, '删除场景失败')
        return false
      }
    },
  },
})
