import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'Dashboard',
      component: () => import('@/views/Dashboard.vue'),
    },
    {
      path: '/ca',
      name: 'RootCA',
      component: () => import('@/views/RootCA.vue'),
    },
    {
      path: '/cert',
      name: 'UserCert',
      component: () => import('@/views/UserCert.vue'),
    },
    {
      path: '/crl',
      name: 'CRL',
      component: () => import('@/views/CRL.vue'),
    },
  ],
})

export default router
