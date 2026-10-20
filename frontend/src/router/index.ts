import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { title: '总览', subtitle: '全屋状态、环境与场景一览' },
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
      meta: { title: 'AI 管家', subtitle: '自然语言控制 · 实时执行轨迹' },
    },
    {
      path: '/devices',
      name: 'devices',
      component: () => import('@/views/DevicesView.vue'),
      meta: { title: '设备', subtitle: '异构设备统一接入与状态控制' },
    },
    {
      path: '/scenes',
      name: 'scenes',
      component: () => import('@/views/ScenesView.vue'),
      meta: { title: '场景编排', subtitle: 'LangGraph 多步编排 · 条件判断与异常兜底' },
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('@/views/KnowledgeView.vue'),
      meta: { title: '知识库', subtitle: '意图示例、RAG 向量检索与家庭知识' },
    },
    {
      path: '/executions',
      name: 'executions',
      component: () => import('@/views/ExecutionsView.vue'),
      meta: { title: '运行轨迹', subtitle: 'Agent 节点耗时、工具调用与执行结果' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

router.afterEach((to) => {
  const title = (to.meta.title as string) || '智慧居'
  document.title = `${title} · 智慧居 AI Agent`
})

export default router
