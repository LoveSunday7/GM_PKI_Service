import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '@/api'

const TOKEN_KEY = 'gm_pki_token'
const USER_KEY = 'gm_pki_user'
const ROLE_KEY = 'gm_pki_role'

function decodeTokenPayload(token: string): { sub?: string; role?: string } | null {
  const payload = token.split('.')[1]
  if (!payload) return null
  try {
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    return JSON.parse(atob(padded)) as { sub?: string; role?: string }
  } catch {
    return null
  }
}

function restoreLocalValue(key: string, fallback?: string) {
  const value = localStorage.getItem(key) || fallback || ''
  if (value) localStorage.setItem(key, value)
  return value
}

export const useAuthStore = defineStore('auth', () => {
  const initialToken = localStorage.getItem(TOKEN_KEY) || ''
  const initialPayload = initialToken ? decodeTokenPayload(initialToken) : null
  const token = ref<string>(initialToken)
  const username = ref<string>(restoreLocalValue(USER_KEY, initialPayload?.sub))
  const role = ref<string>(restoreLocalValue(ROLE_KEY, initialPayload?.role))
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  function persistToken(t: string, u: string, r: string) {
    token.value = t
    username.value = u
    role.value = r
    localStorage.setItem(TOKEN_KEY, t)
    localStorage.setItem(USER_KEY, u)
    localStorage.setItem(ROLE_KEY, r)
  }

  function clearToken() {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(ROLE_KEY)
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
