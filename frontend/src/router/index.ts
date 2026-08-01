import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/views/layout/index.vue'),
    redirect: '/chat',
    children: [
      {
        path: '/chat',
        name: 'Chat',
        component: () => import('@/views/chat/index.vue'),
        meta: { title: '智能问答', icon: 'ChatDotRound' },
      },
      {
        path: '/knowledge',
        name: 'Knowledge',
        component: () => import('@/views/knowledge/index.vue'),
        meta: { title: '知识库管理', icon: 'Collection', admin: true },
      },
      {
        path: '/documents',
        name: 'Documents',
        component: () => import('@/views/documents/index.vue'),
        meta: { title: '文档管理', icon: 'Document', admin: true },
      },
      {
        path: '/users',
        name: 'Users',
        component: () => import('@/views/admin/users.vue'),
        meta: { title: '用户管理', icon: 'User', admin: true },
      },
      {
        path: '/settings',
        name: 'Settings',
        component: () => import('@/views/admin/settings.vue'),
        meta: { title: '系统设置', icon: 'Setting', admin: true },
      },
      {
        path: '/models',
        name: 'Models',
        component: () => import('@/views/admin/models/index.vue'),
        meta: { title: '模型管理', icon: 'Connection', admin: true },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
    meta: { public: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()

  // 公开页面直接放行
  if (to.meta.public) {
    next()
    return
  }

  // 未登录跳转到登录页
  if (!authStore.isLoggedIn) {
    next('/login')
    return
  }

  // 管理员页面权限检查
  if (to.meta.admin && !authStore.isAdmin) {
    next('/chat')
    return
  }

  next()
})

export { routes }
export default router
