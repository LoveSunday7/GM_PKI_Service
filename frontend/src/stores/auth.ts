import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '@/api'

const TOKEN_KEY = 'gm_pki_token'
const USER_KEY = 'gm_pki_user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
  const username = ref<string>(localStorage.getItem(USER_KEY) || '')
  const role = ref<string>('')
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  function persistToken(t: string, u: string, r: string) {
    token.value = t
    username.value = u
    role.value = r
    localStorage.setItem(TOKEN_KEY, t)
    localStorage.setItem(USER_KEY, u)
  }

  function clearToken() {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  async function login(u: string, p: string) {
    loading.value = true
    error.value = null
    try {
      const res = await authApi.login(u, p)
      persistToken(res.access_token, res.username, res.role)
      return res
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '登录失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try {
      if (token.value) {
        await authApi.logout(token.value)
      }
    } catch {
      // ignore logout API errors
    } finally {
      clearToken()
    }
  }

  return { token, username, role, loading, error, isAuthenticated, login, logout, clearToken }
})
