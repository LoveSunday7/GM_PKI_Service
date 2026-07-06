import { ApiError } from '@/api'

/** 业务错误码 → 中文描述 */
const ERROR_MESSAGES: Record<string, string> = {
  AUTH_INVALID_CREDENTIALS: '用户名或密码错误',
  AUTH_TOKEN_EXPIRED: '登录已过期，请重新登录',
  AUTH_TOKEN_INVALID: '认证失败，请重新登录',
  AUTH_TOKEN_BLACKLISTED: 'Token 已失效，请重新登录',
  CA_NOT_INITIALIZED: 'CA 尚未初始化',
  CA_ALREADY_INITIALIZED: 'CA 已初始化，不能重复操作',
  CA_ROOT_CERT_NOT_FOUND: '根证书未找到',
  CERT_NOT_FOUND: '证书未找到',
  CERT_ALREADY_REVOKED: '证书已被撤销',
  CERT_ISSUE_FAILED: '证书签发失败',
  CRL_EMPTY: '暂无撤销记录',
  CRL_GENERATE_FAILED: 'CRL 生成失败',
  VALIDATION_ERROR: '请求参数校验失败',
  INTERNAL_ERROR: '服务器内部错误',
  NOT_FOUND: '资源未找到',
  FORBIDDEN: '权限不足',
  CONFLICT: '操作冲突，资源已存在',
}

/** 根据 ApiError 返回用户可读的错误信息 */
export function formatError(e: unknown): string {
  if (e instanceof ApiError) {
    const prefix = ERROR_MESSAGES[e.errorCode] ? `[${e.errorCode}] ` : ''
    return `${prefix}${ERROR_MESSAGES[e.errorCode] || e.message}`
  }
  if (e instanceof Error) return e.message
  return '未知错误'
}
