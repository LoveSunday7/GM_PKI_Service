const BASE = '/api'
const TOKEN_KEY = 'gm_pki_token'
const USER_KEY = 'gm_pki_user'
const ROLE_KEY = 'gm_pki_role'
const DEFAULT_TIMEOUT = 30_000

interface ApiErrorBody {
  success?: boolean
  error_code?: string
  message?: string
  detail?: unknown
}

export class ApiError extends Error {
  errorCode: string
  statusCode: number

  constructor(statusCode: number, body: ApiErrorBody) {
    const detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? '')
    super(body.message || detail || `HTTP ${statusCode}`)
    this.errorCode = body.error_code || 'UNKNOWN'
    this.statusCode = statusCode
    this.name = 'ApiError'
  }
}

let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(ROLE_KEY)
}

function decodeJwtPayload(token: string): { exp?: number } | null {
  const payload = token.split('.')[1]
  if (!payload) return null
  try {
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    return JSON.parse(atob(padded)) as { exp?: number }
  } catch {
    return null
  }
}

export function isTokenExpired(): boolean {
  const token = getToken()
  if (!token) return true
  const payload = decodeJwtPayload(token)
  return !payload?.exp || Date.now() >= payload.exp * 1000
}

async function request<T>(url: string, options?: RequestInit & { timeout?: number }): Promise<T> {
  const token = getToken()
  const timeout = options?.timeout ?? DEFAULT_TIMEOUT
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  }
  if (token) headers.Authorization = `Bearer ${token}`

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)

  try {
    const res = await fetch(`${BASE}${url}`, { ...options, headers, signal: controller.signal })
    if (!res.ok) {
      if (res.status === 401) {
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

async function download(url: string, filename: string, options?: RequestInit): Promise<void> {
  const token = getToken()
  const headers: Record<string, string> = { ...(options?.headers as Record<string, string>) }
  if (token) headers.Authorization = `Bearer ${token}`

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

export const authApi = {
  login: (username: string, password: string) =>
    request<{ success: boolean; access_token: string; token_type: string; username: string; role: string }>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify({ username, password }) },
    ),
  logout: (token: string) =>
    request<{ success: boolean; message: string }>('/auth/logout', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }),
}

export const caApi = {
  status: () => request<{ initialized: boolean; ca_name?: string; organization?: string }>('/ca/status'),
  initialize: (data: Record<string, unknown>) =>
    request<{ success: boolean; message: string; serial_number: string; subject_dn: string; cert_pem: string }>(
      '/ca/initialize',
      { method: 'POST', body: JSON.stringify(data) },
    ),
  listRootCerts: () =>
    request<
      Array<{
        id: string
        serial_number: string
        subject_dn: string
        signature_algorithm: string
        not_before: string
        not_after: string
        status: string
      }>
    >('/ca/root-cert'),
  reset: () => request<{ success: boolean; message: string }>('/ca/reset', { method: 'POST' }),
  getRootCert: (serial: string) => request<Record<string, unknown>>(`/ca/root-cert/${serial}`),
  downloadRootCert: (serial: string) => download(`/ca/root-cert/${serial}/download`, `root_${serial}.pem`),
}

export interface CertListItem {
  id: string
  serial_number: string
  cert_type: string
  subject_dn: string
  user_name: string
  not_after: string
  status: string
}

export interface CertDetail extends CertListItem {
  issuer_dn: string
  email?: string | null
  issuer_cert_serial?: string | null
  owner_username?: string | null
  signature_algorithm: string
  encryption_algorithm: string
  not_before: string
  cert_pem: string
}

export interface CertIssueResponse {
  success: boolean
  message: string
  subject_dn?: string
  root_dn?: string
  sign_serial_number?: string
  encrypt_serial_number?: string
  serial_number?: string
  cert_pem?: string
  private_key_pem?: string
  issuer_cert_serial?: string | null
}

export interface CertApplicationItem {
  id: string
  user_name: string
  email?: string | null
  organization?: string | null
  department?: string | null
  cert_type: string
  validity_days: number
  status: string
  reject_reason?: string | null
  applied_by: string
  reviewed_by?: string | null
  issued_cert_serial?: string | null
  issued_encrypt_cert_serial?: string | null
  issuer_cert_serial?: string | null
  signature_algorithm: string
  encryption_algorithm: string
  created_at: string
}

export interface CertIssuerItem {
  serial_number: string
  subject_dn: string
  issuer_type: 'root' | 'intermediate_ca'
  display_name: string
}

export interface CertChainNode {
  serial_number: string
  subject_dn: string
  issuer_dn: string
  cert_type: string
  not_before: string
  not_after: string
  status: string
  cert_pem: string
}

export interface CertChainResponse {
  chain: CertChainNode[]
  depth: number
  verified: boolean
}

export interface CertVerifyResult {
  valid: boolean
  details: string
  cert_subject: string
  issuer_subject: string
  serial_number: string
  not_before: string
  not_after: string
  in_validity_period: boolean
  chain?: CertChainNode[] | null
}

export interface CertRevocationVerifyResult {
  revoked: boolean
  reason: string | null
  revocation_date: string | null
  error?: string
}

export const certApi = {
  issue: (data: Record<string, unknown>) =>
    request<CertIssueResponse>('/cert/issue', { method: 'POST', body: JSON.stringify(data) }),
  list: (params?: { cert_type?: string; status?: string; page?: number; page_size?: number }) => {
    const qs = new URLSearchParams()
    if (params?.cert_type) qs.set('cert_type', params.cert_type)
    if (params?.status) qs.set('status', params.status)
    if (params?.page) qs.set('page', String(params.page))
    if (params?.page_size) qs.set('page_size', String(params.page_size))
    const q = qs.toString()
    return request<{ items: CertListItem[]; total: number; page: number; page_size: number }>(
      `/cert/list${q ? `?${q}` : ''}`,
    )
  },
  detail: (serial: string) => request<CertDetail>(`/cert/${serial}`),
  status: (serial: string) =>
    request<{ serial_number: string; status: string; revoked_at?: string; reason?: string }>(
      `/cert/${serial}/status`,
    ),
  download: (serial: string) => download(`/cert/${serial}/download`, `${serial}.pem`),
  stats: () =>
    request<{
      total: number
      active: number
      revoked: number
      sign: number
      encrypt: number
      expiring_soon: number
      today_issued: number
    }>('/cert/stats'),
  activity: () =>
    request<{ activities: Array<{ type: string; time: string; user: string; serial: string; detail: string }> }>(
      '/cert/activity',
    ),
  issuers: () => request<CertIssuerItem[]>('/cert/issuers'),
  apply: (data: {
    user_name: string
    email?: string
    organization?: string
    department?: string
    province?: string
    city?: string
    cert_type: string
    validity_days: number
    public_key_pem?: string
    signature_algorithm?: string
    encryption_algorithm?: string
    issuer_cert_serial?: string
  }) =>
    request<{ success: boolean; message: string; application_id: string }>('/cert/apply', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  applications: (params?: { status?: string; page?: number; page_size?: number }) => {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.page) qs.set('page', String(params.page))
    if (params?.page_size) qs.set('page_size', String(params.page_size))
    const q = qs.toString()
    return request<{ items: CertApplicationItem[]; total: number; page: number; page_size: number }>(
      `/cert/applications${q ? `?${q}` : ''}`,
    )
  },
  approve: (id: string) =>
    request<{ success: boolean; message: string; application_id: string; issued_cert_serial?: string }>(
      `/cert/applications/${id}/approve`,
      { method: 'POST', body: '{}' },
    ),
  reject: (id: string, reason: string) =>
    request<{ success: boolean; message: string; application_id: string }>(`/cert/applications/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  chain: (serial: string) =>
    request<CertChainResponse>(`/cert/${serial}/chain`),
  verify: (data: { cert_pem?: string; serial_number?: string; issuer_cert_pem?: string; show_chain?: boolean }) =>
    request<CertVerifyResult>('/cert/verify', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  verifyRevocation: (certPem: string, crlPem: string) =>
    request<CertRevocationVerifyResult>('/cert/verify-revocation', {
      method: 'POST',
      body: JSON.stringify({ cert_pem: certPem, crl_pem: crlPem }),
    }),
}

export interface SystemConfig {
  app_name: string
  debug: boolean
  database_type: string
  keystore_dir: string
  log_level: string
  ca_name: string
  organization: string
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
  getConfig: () => request<SystemConfig>('/system/config'),
  getKeystoreInfo: () => request<KeystoreInfo>('/system/keystore-info'),
  getDatabase: () => request<DatabaseInfo>('/system/database'),
  getLogs: (params?: { lines?: number; level?: string }) => {
    const qs = new URLSearchParams()
    if (params?.lines) qs.set('lines', String(params.lines))
    if (params?.level) qs.set('level', params.level)
    const q = qs.toString()
    return request<LogQueryResponse>(`/system/logs${q ? `?${q}` : ''}`)
  },
  downloadLogs: () => download('/system/logs/download', 'app.log'),
  updateLogLevel: (level: string) =>
    request<{ success: boolean; previous_level: string; current_level: string; message: string }>('/system/log-level', {
      method: 'PUT',
      body: JSON.stringify({ level }),
    }),
  updateConfig: (
    data: Partial<
      Pick<
        SystemConfig,
        | 'keystore_dir'
        | 'ca_name'
        | 'organization'
        | 'default_signature_algorithm'
        | 'ca_default_validity_days'
        | 'cert_default_validity_days'
        | 'crl_validity_hours'
      >
    >,
  ) =>
    request<
      {
        success: boolean
        message: string
        updated_fields: string[]
      } & Pick<
        SystemConfig,
        | 'keystore_dir'
        | 'ca_name'
        | 'organization'
        | 'ca_default_validity_days'
        | 'cert_default_validity_days'
        | 'crl_validity_hours'
        | 'default_signature_algorithm'
      >
    >('/system/config', { method: 'PUT', body: JSON.stringify(data) }),
}

export interface AdminUserItem {
  id: string
  username: string
  role: string
  created_at: string
}

export interface RevocationApplicationItem {
  id: string
  cert_serial_number: string
  reason: string
  description?: string | null
  status: string
  reject_reason?: string | null
  applied_by: string
  reviewed_by?: string | null
  created_at: string
}

export const adminApi = {
  list: () => request<AdminUserItem[]>('/admin/users'),
  create: (data: { username: string; password: string; role: string }) =>
    request<{ success: boolean; message: string; username: string; role: string }>('/admin/users', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  delete: (username: string) =>
    request<{ success: boolean; message: string; username: string }>(`/admin/users/${username}`, {
      method: 'DELETE',
    }),
  changePassword: (username: string, newPassword: string) =>
    request<{ success: boolean; message: string; username: string }>(`/admin/users/${username}/password`, {
      method: 'PUT',
      body: JSON.stringify({ new_password: newPassword }),
    }),
}

export const crlApi = {
  revoke: (data: { cert_serial_number: string; reason: string }) =>
    request<{ success: boolean; message: string; cert_serial_number: string; reason: string; revoked_at: string }>(
      '/crl/revoke',
      { method: 'POST', body: JSON.stringify(data) },
    ),
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
    request<
      | {
          crl_number: number
          issuer_dn: string
          this_update: string
          next_update: string
          signature_algorithm: string
          revoked_count: number
          crl_pem: string
          revoked_certificates: Array<{ cert_serial_number: string; reason: string; revoked_at: string }>
          created_at: string
        }
      | { message: string; crl_number: number; revoked_count: number }
    >('/crl/current'),
  download: () => download('/crl/download', 'crl.pem'),
  history: (page = 1, pageSize = 10) =>
    request<{
      items: Array<{
        id: string
        crl_number: number
        issuer_dn: string
        this_update: string
        next_update: string
        signature_algorithm: string
        revoked_count: number
        created_at: string
      }>
      total: number
      page: number
      page_size: number
    }>(`/crl/history?page=${page}&page_size=${pageSize}`),
  applyRevocation: (data: { cert_serial_number: string; reason: string; description?: string }) =>
    request<{ success: boolean; message: string; application_id: string }>('/crl/revoke-applications', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  revocationApplications: (params?: { status?: string; page?: number; page_size?: number }) => {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.page) qs.set('page', String(params.page))
    if (params?.page_size) qs.set('page_size', String(params.page_size))
    const q = qs.toString()
    return request<{ items: RevocationApplicationItem[]; total: number; page: number; page_size: number }>(
      `/crl/revoke-applications${q ? `?${q}` : ''}`,
    )
  },
  approveRevocation: (id: string) =>
    request<{ success: boolean; message: string; application_id: string; cert_serial_number?: string }>(
      `/crl/revoke-applications/${id}/approve`,
      { method: 'POST', body: '{}' },
    ),
  rejectRevocation: (id: string, rejectReason: string) =>
    request<{ success: boolean; message: string; application_id: string; cert_serial_number?: string }>(
      `/crl/revoke-applications/${id}/reject`,
      { method: 'POST', body: JSON.stringify({ reject_reason: rejectReason }) },
    ),
}
