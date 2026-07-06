import { createRouter, createWebHistory } from 'vue-router'
import { isTokenExpired, setUnauthorizedHandler } from '@/api'

const TOKEN_KEY = 'gm_pki_token'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
      meta: { guest: true },
    },
    {
      path: '/',
      name: 'Dashboard',
      component: () => import('@/views/Dashboard.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/ca',
      name: 'RootCA',
      component: () => import('@/views/RootCA.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/cert',
      name: 'UserCert',
      component: () => import('@/views/UserCert.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/crl',
      name: 'CRL',
      component: () => import('@/views/CRL.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach((to) => {
  const hasToken = !!localStorage.getItem(TOKEN_KEY)
  const expired = hasToken && isTokenExpired()

  // Token 已过期 → 清理并重定向登录
  if (hasToken && expired) {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem('gm_pki_user')
    return { name: 'Login', query: { redirect: to.fullPath, reason: 'expired' } }
  }

  // 未登录访问受保护页面
  if (to.meta.requiresAuth && !hasToken) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  // 已登录访问登录页
  if (to.meta.guest && hasToken && !expired) {
    return { name: 'Dashboard' }
  }
})

// 注册 API 401 回调 — 后端返回 401 时自动跳转登录页
setUnauthorizedHandler(() => {
  router.push({ name: 'Login', query: { reason: 'expired' } })
})

export default router
