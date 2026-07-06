/** 统一 API 客户端 — 所有后端请求均通过此模块发出. */

const BASE = '/api'
const TOKEN_KEY = 'gm_pki_token'

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(options?.headers as Record<string, string> || {}) }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetch(`${BASE}${url}`, { ...options, headers })
  if (!res.ok) {
    // 401 — clear stale token
    if (res.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
    }
    const body = await res.json().catch(() => ({ message: res.statusText }))
    throw new Error(body.message || body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ── 认证 ───────────────────────────────────────────────────────────

export const authApi = {
  login: (username: string, password: string) =>
    request<{ success: boolean; access_token: string; token_type: string; username: string; role: string }>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify({ username, password }) },
    ),
  logout: (token: string) =>
    request('/auth/logout', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }),
}

// ── CA 根证书 ────────────────────────────────────────────────────

export const caApi = {
  status: () => request<{ initialized: boolean; ca_name?: string }>('/ca/status'),
  initialize: (data: Record<string, unknown>) =>
    request('/ca/initialize', { method: 'POST', body: JSON.stringify(data) }),
  listRootCerts: () => request('/ca/root-cert'),
  getRootCert: (serial: string) => request(`/ca/root-cert/${serial}`),
}

// ── 用户证书 ─────────────────────────────────────────────────────

export const certApi = {
  issue: (data: Record<string, unknown>) =>
    request('/cert/issue', { method: 'POST', body: JSON.stringify(data) }),
  list: (params?: { cert_type?: string; status?: string }) => {
    const qs = new URLSearchParams()
    if (params?.cert_type) qs.set('cert_type', params.cert_type)
    if (params?.status) qs.set('status', params.status)
    const q = qs.toString()
    return request(`/cert/list${q ? `?${q}` : ''}`)
  },
  detail: (serial: string) => request(`/cert/${serial}`),
  status: (serial: string) => request(`/cert/${serial}/status`),
}

// ── CRL 撤销列表 ─────────────────────────────────────────────────

export const crlApi = {
  revoke: (data: { cert_serial_number: string; reason: string }) =>
    request('/crl/revoke', { method: 'POST', body: JSON.stringify(data) }),
  generate: () => request('/crl/generate', { method: 'POST' }),
  current: () => request('/crl/current'),
}
