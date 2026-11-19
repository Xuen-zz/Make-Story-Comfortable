import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'workflow',
      component: () => import('@/views/WorkflowCanvasView.vue'),
      meta: { title: '节点工作流画布' },
    },
    {
      path: '/workshop',
      name: 'workshop',
      component: () => import('@/views/WorkshopView.vue'),
      meta: { title: '写书工单台' },
    },
    {
      path: '/workflow',
      redirect: '/',
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsHubView.vue'),
      meta: { title: '资产与系统设置' },
    },
    {
      path: '/assets',
      name: 'assets',
      component: () => import('@/views/AssetsHubView.vue'),
      meta: { title: '创作资产库' },
    },
    {
      path: '/system',
      name: 'system',
      component: () => import('@/views/SystemHubView.vue'),
      meta: { title: '系统与工具' },
    },
    {
      path: '/config',
      name: 'config',
      component: () => import('@/views/ConfigView.vue'),
      meta: { title: '模型配置' },
    },
    {
      path: '/presets',
      name: 'presets',
      component: () => import('@/views/PresetsView.vue'),
      meta: { title: '提示词方案' },
    },
    {
      path: '/styles',
      name: 'styles',
      component: () => import('@/views/StylesView.vue'),
      meta: { title: '文风与DNA' },
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('@/views/KnowledgeView.vue'),
      meta: { title: '知识库' },
    },
    {
      path: '/consistency',
      name: 'consistency',
      component: () => import('@/views/ConsistencyView.vue'),
      meta: { title: '一致性检查' },
    },
    {
      path: '/files',
      name: 'files',
      component: () => import('@/views/FilesView.vue'),
      meta: { title: '文件管理' },
    },
    {
      path: '/reader',
      name: 'reader',
      component: () => import('@/views/ReaderView.vue'),
      meta: { title: '小说阅读' },
    },
    {
      path: '/brainstorm',
      name: 'brainstorm',
      component: () => import('@/views/BrainstormView.vue'),
      meta: { title: '创意讨论' },
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('@/views/ProfileView.vue'),
      meta: { title: '用户画像' },
    },
    {
      path: '/logs',
      name: 'logs',
      component: () => import('@/views/LogsView.vue'),
      meta: { title: '运行日志' },
    },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title ?? 'NovelWriter'} — NovelWriter`
})

export default router
