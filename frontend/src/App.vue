<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import ToastContainer from '@/components/ToastContainer.vue'

const route = useRoute()
const isLoginPage = computed(() => route.name === 'Login')
</script>

<template>
  <!-- Toast 全局通知 -->
  <ToastContainer />

  <!-- 登录页：全屏，无布局 -->
  <RouterView v-if="isLoginPage" />

  <!-- 管理页：侧边栏 + 顶栏 + 内容区 -->
  <DefaultLayout v-else />
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
