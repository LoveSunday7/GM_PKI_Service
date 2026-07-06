<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const submitting = ref(false)
const errorMsg = ref('')

// 来自路由守卫的提示信息
const expiredMsg = route.query.reason === 'expired' ? '会话已过期，请重新登录' : ''

async function handleLogin() {
  if (!username.value.trim() || !password.value.trim()) {
    errorMsg.value = '请输入用户名和密码'
    return
  }
  submitting.value = true
  errorMsg.value = ''
  try {
    await authStore.login(username.value.trim(), password.value)
    // 登录成功后跳转到原始目标页或首页
    const redirect = route.query.redirect as string | undefined
    router.replace(redirect || { name: 'Dashboard' })
  } catch (e: any) {
    errorMsg.value = e.message || '登录失败，请检查用户名和密码'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-wrapper">
    <div class="login-card">
      <div class="login-header">
        <h1>GM PKI Service</h1>
        <p>基于国密算法的 PKI 体系数字证书认证系统</p>
      </div>
      <p v-if="expiredMsg" class="info-msg">{{ expiredMsg }}</p>
      <form class="login-form" @submit.prevent="handleLogin">
        <div class="field">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="username"
            type="text"
            placeholder="请输入用户名"
            autocomplete="username"
            :disabled="submitting"
          />
        </div>
        <div class="field">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="请输入密码"
            autocomplete="current-password"
            :disabled="submitting"
          />
        </div>
        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
        <button type="submit" class="btn-login" :disabled="submitting">
          {{ submitting ? '登录中...' : '登 录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}

.login-card {
  background: #fff;
  border-radius: 16px;
  padding: 3rem 2.5rem;
  width: 100%;
  max-width: 420px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
}

.login-header {
  text-align: center;
  margin-bottom: 2rem;
}

.login-header h1 {
  font-size: 1.6rem;
  font-weight: 700;
  color: #1a1a2e;
  margin-bottom: 0.5rem;
}

.login-header p {
  font-size: 0.85rem;
  color: #888;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.field label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #333;
}

.field input {
  padding: 0.7rem 0.85rem;
  border: 1.5px solid #e0e0e0;
  border-radius: 8px;
  font-size: 0.95rem;
  transition: border-color 0.2s;
  outline: none;
}

.field input:focus {
  border-color: #0f3460;
}

.field input:disabled {
  background: #f5f5f5;
  cursor: not-allowed;
}

.info-msg {
  color: #e65100;
  font-size: 0.85rem;
  text-align: center;
  padding: 0.5rem;
  background: #fff3e0;
  border-radius: 6px;
  margin-bottom: 0.5rem;
}

.error-msg {
  color: #d32f2f;
  font-size: 0.85rem;
  text-align: center;
  padding: 0.5rem;
  background: #fdecea;
  border-radius: 6px;
}

.btn-login {
  padding: 0.75rem;
  background: linear-gradient(135deg, #1a1a2e, #0f3460);
  color: #fff;
  font-size: 1rem;
  font-weight: 600;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn-login:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-login:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
