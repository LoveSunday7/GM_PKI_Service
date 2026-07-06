import { createRouter, createWebHistory } from 'vue-router'

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

  if (to.meta.requiresAuth && !hasToken) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  if (to.meta.guest && hasToken) {
    return { name: 'Dashboard' }
  }
})

export default router
