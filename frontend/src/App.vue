<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const isLoginPage = computed(() => route.name === 'Login')

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}
</script>

<template>
  <!-- 登录页：无侧边栏，全屏展示 -->
  <div v-if="isLoginPage">
    <RouterView />
  </div>

  <!-- 管理页：带侧边栏布局 -->
  <div v-else class="app-layout">
    <aside class="sidebar">
      <h1 class="logo">GM PKI</h1>
      <nav>
        <RouterLink to="/">📊 Dashboard</RouterLink>
        <RouterLink to="/ca">🔐 Root CA</RouterLink>
        <RouterLink to="/cert">📜 Certificates</RouterLink>
        <RouterLink to="/crl">🚫 CRL</RouterLink>
      </nav>
      <div class="sidebar-footer">
        <span class="user-info" v-if="authStore.username">{{ authStore.username }}</span>
        <button class="btn-logout" @click="handleLogout">退出</button>
      </div>
    </aside>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}
body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: #f0f2f5;
  color: #1a1a2e;
}
</style>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 240px;
  background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
  color: #fff;
  padding: 1.5rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  flex-shrink: 0;
}
.logo {
  font-size: 1.3rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-align: center;
  padding-bottom: 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
}
nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
nav a {
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  padding: 0.6rem 0.75rem;
  border-radius: 8px;
  font-size: 0.95rem;
  transition: all 0.2s;
}
nav a:hover,
nav a.router-link-exact-active {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}
.sidebar-footer {
  margin-top: auto;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.15);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.user-info {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.7);
  text-align: center;
}
.btn-logout {
  padding: 0.5rem;
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
}
.btn-logout:hover {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
}
.content {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
}
</style>
