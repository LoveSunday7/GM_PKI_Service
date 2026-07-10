<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}

const navItems = [
  { to: '/', label: '仪表盘', icon: '📊', adminOnly: true },
  { to: '/ca', label: '根 CA', icon: '🔐', adminOnly: true },
  { to: '/multi-ca', label: '多级证书', icon: '🔗', adminOnly: true },
  { to: '/cert', label: authStore.role === 'admin' ? '证书一览' : '我的证书', icon: '📜' },
  { to: '/cert-apply', label: '证书申请', icon: '📝', userOnly: true },
  { to: '/cert-audit', label: '申请审核', icon: '🔍', adminOnly: true },
  { to: '/crl', label: authStore.role === 'admin' ? 'CRL 发布' : '撤销申请', icon: '🚫' },
  { to: '/verify', label: '证书验证', icon: '🔍' },
  { to: '/admin-users', label: '账户管理', icon: '👥', adminOnly: true },
  { to: '/settings', label: '系统设置', icon: '⚙️', adminOnly: true },
]
</script>

<template>
  <div class="app-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-brand">
        <span class="brand-icon">🛡️</span>
        <span class="brand-text">GM PKI</span>
      </div>

      <nav class="sidebar-nav">
        <RouterLink
          v-for="item in navItems"
          v-show="(!item.adminOnly || authStore.role === 'admin') && (!item.userOnly || authStore.role !== 'admin')"
          :key="item.to"
          :to="item.to"
          class="nav-link"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <div class="user-badge" v-if="authStore.username">
          <span class="user-avatar">{{ authStore.username.charAt(0).toUpperCase() }}</span>
          <span class="user-name">{{ authStore.username }}</span>
          <span class="user-role">{{ authStore.role }}</span>
        </div>
        <button class="btn-logout" @click="handleLogout">
          <span>⏻</span> 退出登录
        </button>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main">
      <header class="topbar">
        <h2 class="page-title">{{ route.meta.title || route.name }}</h2>
      </header>
      <div class="content">
        <RouterView />
      </div>
    </main>
  </div>
</template>

<style scoped>
/* ── 布局 ─────────────────────────────────────────────── */
.app-layout {
  display: flex;
  min-height: 100vh;
}

/* ── 侧边栏 ──────────────────────────────────────────── */
.sidebar {
  width: 240px;
  background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
  color: #fff;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1.5rem 1.25rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.brand-icon {
  font-size: 1.5rem;
}

.brand-text {
  font-size: 1.2rem;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.sidebar-nav {
  flex: 1;
  padding: 0.75rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  overflow-y: auto;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.65);
  text-decoration: none;
  font-size: 0.9rem;
  transition: all 0.15s;
}

.nav-link:hover {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.9);
}

.nav-link.router-link-exact-active,
.nav-link.router-link-active[to="/"] {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-weight: 600;
}

.nav-icon {
  font-size: 1.1rem;
  width: 1.5rem;
  text-align: center;
}

/* ── 侧边栏底部 ──────────────────────────────────────── */
.sidebar-footer {
  padding: 1rem 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.user-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  font-weight: 700;
  flex-shrink: 0;
}

.user-name {
  font-size: 0.85rem;
  font-weight: 500;
}

.user-role {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.5);
  background: rgba(255, 255, 255, 0.1);
  padding: 0.1rem 0.4rem;
  border-radius: 10px;
}

.btn-logout {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0.5rem;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.82rem;
  transition: all 0.15s;
}

.btn-logout:hover {
  background: rgba(220, 53, 69, 0.25);
  border-color: rgba(220, 53, 69, 0.4);
  color: #f8d7da;
}

/* ── 主内容区 ────────────────────────────────────────── */
.main {
  flex: 1;
  margin-left: 240px;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #f0f2f5;
}

.topbar {
  background: #fff;
  padding: 1rem 2rem;
  border-bottom: 1px solid #e8e8e8;
  position: sticky;
  top: 0;
  z-index: 50;
}

.page-title {
  font-size: 1.15rem;
  font-weight: 600;
  color: #1a1a2e;
}

.content {
  flex: 1;
  padding: 1.5rem 2rem;
}
</style>
