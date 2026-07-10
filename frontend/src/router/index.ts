import { createRouter, createWebHistory } from 'vue-router'
import { isTokenExpired, setUnauthorizedHandler } from '@/api'

const TOKEN_KEY = 'gm_pki_token'
const ROLE_KEY = 'gm_pki_role'

function roleFromToken(token: string): string {
  const cached = localStorage.getItem(ROLE_KEY)
  if (cached) return cached
  const payload = token.split('.')[1]
  if (!payload) return ''
  try {
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    const decoded = JSON.parse(atob(padded)) as { role?: string }
    if (decoded.role) localStorage.setItem(ROLE_KEY, decoded.role)
    return decoded.role || ''
  } catch {
    return ''
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'Login', component: () => import('@/views/Login.vue'), meta: { guest: true, title: '登录' } },
    { path: '/', name: 'Dashboard', component: () => import('@/views/Dashboard.vue'), meta: { requiresAuth: true, requiresAdmin: true, title: '系统概览' } },
    { path: '/ca', name: 'RootCA', component: () => import('@/views/RootCA.vue'), meta: { requiresAuth: true, requiresAdmin: true, title: '根 CA 管理' } },
    { path: '/multi-ca', name: 'MultiLevelCA', component: () => import('@/views/MultiLevelCA.vue'), meta: { requiresAuth: true, requiresAdmin: true, title: '多级证书' } },
    { path: '/cert', name: 'UserCert', component: () => import('@/views/UserCert.vue'), meta: { requiresAuth: true, title: '证书一览' } },
    { path: '/crl', name: 'CRL', component: () => import('@/views/CRL.vue'), meta: { requiresAuth: true, title: '证书撤销 / CRL' } },
    { path: '/verify', name: 'CertVerify', component: () => import('@/views/CertVerify.vue'), meta: { requiresAuth: true, title: '证书验证' } },
    { path: '/cert-apply', name: 'CertApply', component: () => import('@/views/CertApply.vue'), meta: { requiresAuth: true, title: '证书申请' } },
    { path: '/cert-audit', name: 'CertAudit', component: () => import('@/views/CertAudit.vue'), meta: { requiresAuth: true, requiresAdmin: true, title: '申请审核' } },
    { path: '/admin-users', name: 'AdminUsers', component: () => import('@/views/AdminUsers.vue'), meta: { requiresAuth: true, requiresAdmin: true, title: '账户管理' } },
    { path: '/settings', name: 'Settings', component: () => import('@/views/Settings.vue'), meta: { requiresAuth: true, requiresAdmin: true, title: '系统设置' } },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem(TOKEN_KEY) || ''
  const hasToken = !!token
  const expired = hasToken && isTokenExpired()

  if (hasToken && expired) {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem('gm_pki_user')
    localStorage.removeItem(ROLE_KEY)
    return { name: 'Login', query: { redirect: to.fullPath, reason: 'expired' } }
  }

  if (to.meta.requiresAuth && !hasToken) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  if (to.meta.requiresAdmin && roleFromToken(token) !== 'admin') {
    return { name: 'UserCert' }
  }

  if (to.meta.guest && hasToken && !expired) {
    return roleFromToken(token) === 'admin' ? { name: 'Dashboard' } : { name: 'UserCert' }
  }
})

setUnauthorizedHandler(() => {
  router.push({ name: 'Login', query: { reason: 'expired' } })
})

export default router
