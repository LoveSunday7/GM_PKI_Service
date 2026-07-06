/** 统一 API 客户端 — Token 注入、超时、错误转换、文件下载. */

const BASE = '/api'
const TOKEN_KEY = 'gm_pki_token'
const USER_KEY = 'gm_pki_user'
const DEFAULT_TIMEOUT = 30_000 // 30 秒

/** 后端统一错误响应结构. */
interface ApiErrorBody {
  success?: boolean
  error_code?: string
  message?: string
  detail?: unknown
}

/** 抛出的 API 错误 — 携带后端错误码. */
export class ApiError extends Error {
  errorCode: string
  statusCode: number

  constructor(statusCode: number, body: ApiErrorBody) {
    super(body.message || body.detail?.toString() || `HTTP ${statusCode}`)
    this.errorCode = body.error_code || 'UNKNOWN'
    this.statusCode = statusCode
    this.name = 'ApiError'
  }
}

// ── 拦截器回调 ─────────────────────────────────────────────────

/** 401 时触发跳转登录页的回调，由路由模块注入. */
let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

// ── Token 工具 ─────────────────────────────────────────────────

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

/** 解析 JWT 获取过期时间，若无法解析或已过期返回 true. */
export function isTokenExpired(): boolean {
  const token = getToken()
  if (!token) return true
  try {
    const parts = token.split('.')
    const payloadBase64 = parts[1]
    if (!payloadBase64) return true
    const payload = JSON.parse(atob(payloadBase64))
    const exp: number | undefined = payload.exp
    if (!exp) return true
    return Date.now() >= exp * 1000
  } catch {
    return true
  }
}

function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

// ── 核心请求 ───────────────────────────────────────────────────

async function request<T>(
  url: string,
  options?: RequestInit & { timeout?: number },
): Promise<T> {
  const token = getToken()
  const timeout = options?.timeout ?? DEFAULT_TIMEOUT

  // 构建请求头 — 自动注入 Token
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // 超时控制
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)

  try {
    const res = await fetch(`${BASE}${url}`, {
      ...options,
      headers,
      signal: controller.signal,
    })

    if (!res.ok) {
      // 401 / 403 → 清除认证状态并触发跳转
      if (res.status === 401 || res.status === 403) {
        clearAuth()
        onUnauthorized?.()
      }
      const body: ApiErrorBody = await res.json().catch(() => ({}))
      throw new ApiError(res.status, body)
    }

    return (await res.json()) as T
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('请求超时，请检查网络连接')
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

/** 文件下载 — 返回 Blob，用于证书 / CRL 文件导出. */
async function download(
  url: string,
  filename: string,
  options?: RequestInit,
): Promise<void> {
  const token = getToken()
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string>),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${BASE}${url}`, { ...options, headers })
  if (!res.ok) {
    if (res.status === 401) {
      clearAuth()
      onUnauthorized?.()
    }
    const body: ApiErrorBody = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body)
  }

  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(a.href)
}

// ═══════════════════════════════════════════════════════════════
// 认证
// ═══════════════════════════════════════════════════════════════

export const authApi = {
  login: (username: string, password: string) =>
    request<{
      success: boolean
      access_token: string
      token_type: string
      username: string
      role: string
    }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  logout: (token: string) =>
    request<{ success: boolean; message: string }>('/auth/logout', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }),
}

// ═══════════════════════════════════════════════════════════════
// CA 根证书
// ═══════════════════════════════════════════════════════════════

export const caApi = {
  status: () =>
    request<{ initialized: boolean; ca_name?: string; organization?: string }>(
      '/ca/status',
    ),

  initialize: (data: Record<string, unknown>) =>
    request<{
      success: boolean
      message: string
      serial_number: string
      subject_dn: string
      cert_pem: string
    }>('/ca/initialize', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listRootCerts: () =>
    request<{ id: string; serial_number: string; subject_dn: string; signature_algorithm: string; not_before: string; not_after: string; status: string }[]>('/ca/root-cert'),

  getRootCert: (serial: string) =>
    request<Record<string, unknown>>(`/ca/root-cert/${serial}`),

  downloadRootCert: (serial: string) =>
    download(`/ca/root-cert/${serial}/download`, `root_${serial}.pem`),
}

// ═══════════════════════════════════════════════════════════════
// 用户证书
// ═══════════════════════════════════════════════════════════════

export const certApi = {
  issue: (data: Record<string, unknown>) =>
    request<{
      success: boolean
      message: string
      serial_number: string
      subject_dn: string
      cert_pem: string
      public_key_pem: string | null
      key_pem: string | null
      root_cert_pem: string
    }>('/cert/issue', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  list: (params?: { cert_type?: string; status?: string }) => {
    const qs = new URLSearchParams()
    if (params?.cert_type) qs.set('cert_type', params.cert_type)
    if (params?.status) qs.set('status', params.status)
    const q = qs.toString()
    return request<{ id: string; serial_number: string; cert_type: string; subject_dn: string; user_name: string; not_after: string; status: string }[]>(`/cert/list${q ? `?${q}` : ''}`)
  },

  detail: (serial: string) => request<Record<string, unknown>>(`/cert/${serial}`),

  status: (serial: string) =>
    request<{ serial_number: string; status: string; revoked_at?: string; reason?: string }>(
      `/cert/${serial}/status`,
    ),

  download: (serial: string) =>
    download(`/cert/${serial}/download`, `${serial}.pem`),
}

// ═══════════════════════════════════════════════════════════════
// 系统配置
// ═══════════════════════════════════════════════════════════════

export interface SystemConfig {
  app_name: string
  debug: boolean
  database_type: string
  keystore_dir: string
  log_level: string
  ca_default_validity_days: number
  cert_default_validity_days: number
  crl_validity_hours: number
  default_signature_algorithm: string
}

export interface KeystoreInfo {
  path: string
  file_count: number
  files: Array<{ name: string; size_bytes: number; size_display: string }>
  total_size_bytes: number
  total_size_display: string
}

export interface DatabaseInfo {
  database_type: string
  connected: boolean
  tables: Array<{ name: string; row_count: number }>
  total_rows: number
}

export interface LogQueryResponse {
  log_file: string
  total_lines: number
  requested_lines: number
  level_filter: string | null
  lines: string[]
}

export const systemApi = {
  getConfig: () =>
    request<SystemConfig>('/system/config'),

  getKeystoreInfo: () =>
    request<KeystoreInfo>('/system/keystore-info'),

  getDatabase: () =>
    request<DatabaseInfo>('/system/database'),

  getLogs: (params?: { lines?: number; level?: string }) => {
    const qs = new URLSearchParams()
    if (params?.lines) qs.set('lines', String(params.lines))
    if (params?.level) qs.set('level', params.level)
    const q = qs.toString()
    return request<LogQueryResponse>(`/system/logs${q ? `?${q}` : ''}`)
  },

  downloadLogs: () =>
    download('/system/logs/download', 'app.log'),

  updateLogLevel: (level: string) =>
    request<{ success: boolean; previous_level: string; current_level: string; message: string }>(
      '/system/log-level',
      { method: 'PUT', body: JSON.stringify({ level }) },
    ),

  updateConfig: (data: Partial<Pick<SystemConfig, 'ca_default_validity_days' | 'cert_default_validity_days' | 'crl_validity_hours'>>) =>
    request<{
      success: boolean
      message: string
      updated_fields: string[]
      ca_default_validity_days: number
      cert_default_validity_days: number
      crl_validity_hours: number
    }>('/system/config', { method: 'PUT', body: JSON.stringify(data) }),
}

// ═══════════════════════════════════════════════════════════════
// CRL 撤销列表
// ═══════════════════════════════════════════════════════════════

export const crlApi = {
  revoke: (data: { cert_serial_number: string; reason: string }) =>
    request<{
      success: boolean
      message: string
      cert_serial_number: string
      reason: string
      revoked_at: string
    }>('/crl/revoke', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  generate: () =>
    request<{
      success: boolean
      message: string
      crl_number: number
      this_update: string
      next_update: string
      revoked_count: number
      crl_pem: string
    }>('/crl/generate', { method: 'POST' }),

  current: () =>
    request<{
      crl_number: number
      issuer_dn: string
      this_update: string
      next_update: string
      signature_algorithm: string
      revoked_count: number
      crl_pem: string
      revoked_certificates: Array<{
        cert_serial_number: string
        reason: string
        revoked_at: string
      }>
      created_at: string
    } | { message: string; crl_number: number; revoked_count: number }>('/crl/current'),

  download: () =>
    download('/crl/download', `crl.pem`),
}
