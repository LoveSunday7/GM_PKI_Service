<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="app-layout">
    <aside class="sidebar">
      <h1 class="logo">GM PKI</h1>
      <nav>
        <RouterLink to="/">📊 Dashboard</RouterLink>
        <RouterLink to="/ca">🔐 Root CA</RouterLink>
        <RouterLink to="/cert">📜 Certificates</RouterLink>
        <RouterLink to="/crl">🚫 CRL</RouterLink>
      </nav>
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
.content {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
}
</style>
