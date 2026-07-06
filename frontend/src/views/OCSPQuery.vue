<script setup lang="ts">
import { ref } from 'vue'

defineOptions({ name: 'OCSPQueryPage' })

const serial = ref('')
const loading = ref(false)
const error = ref('')

interface OCSPResult {
  success?: boolean
  cert_serial_number?: string
  status?: string
  status_label?: string
  this_update?: string
  next_update?: string
  revocation_time?: string
  revocation_reason?: string
  signature_algorithm?: string
  signature_value?: string
}

const result = ref<OCSPResult | null>(null)

const reasonLabels: Record<string, string> = {
  unspecified: '未指定',
  keyCompromise: '密钥泄露',
  affiliationChanged: '隶属关系变更',
  superseded: '已被取代',
  cessationOfOperation: '停止运营',
}

async function queryOCSP() {
  if (!serial.value.trim()) {
    error.value = '请输入证书序列号'
    return
  }
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const res = await fetch('/api/ocsp/query', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('gm_pki_token')}`,
      },
      body: JSON.stringify({ cert_serial_number: serial.value.trim() }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.message || body.detail || `HTTP ${res.status}`)
    }
    result.value = await res.json()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '查询失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="ocsp-query">
    <h2>OCSP 证书状态查询</h2>
    <p class="desc">实时查询单张证书的当前状态（正常 / 撤销 / 未知）</p>

    <section class="section">
      <div class="query-bar">
        <input
          v-model="serial"
          type="text"
          placeholder="输入证书序列号（十六进制）..."
          class="serial-input"
          @keyup.enter="queryOCSP"
          :disabled="loading"
        />
        <button class="btn" @click="queryOCSP" :disabled="loading">
          {{ loading ? '查询中...' : '查询状态' }}
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </section>

    <section class="section" v-if="result">
      <div class="result-header" :class="'result-' + result.status">
        <span class="result-icon">
          {{ result.status === 'good' ? '✅' : result.status === 'revoked' ? '🚫' : '❓' }}
        </span>
        <span class="result-label">{{ result.status_label }}</span>
        <span class="result-code">({{ result.status }})</span>
      </div>

      <dl class="detail-grid">
        <dt>证书序列号</dt>
        <dd><code>{{ result.cert_serial_number }}</code></dd>
        <dt>本次查询时间</dt>
        <dd>{{ result.this_update ? new Date(result.this_update).toLocaleString() : '-' }}</dd>
        <dt>建议下次查询</dt>
        <dd>{{ result.next_update ? new Date(result.next_update).toLocaleString() : '-' }}</dd>

        <template v-if="result.status === 'revoked'">
          <dt>撤销时间</dt>
          <dd>{{ result.revocation_time ? new Date(result.revocation_time).toLocaleString() : '-' }}</dd>
          <dt>撤销原因</dt>
          <dd>{{ reasonLabels[result.revocation_reason || ''] || result.revocation_reason || '-' }}</dd>
        </template>

        <template v-if="result.signature_value">
          <dt>签名算法</dt>
          <dd>{{ result.signature_algorithm }}</dd>
          <dt>签名值</dt>
          <dd><code class="sig">{{ result.signature_value?.slice(0, 64) }}...</code></dd>
        </template>
      </dl>
    </section>

    <section class="section info">
      <h3>说明</h3>
      <ul>
        <li><strong>正常 (good)</strong> — 证书有效，未被撤销</li>
        <li><strong>撤销 (revoked)</strong> — 证书已被 CA 撤销</li>
        <li><strong>未知 (unknown)</strong> — 系统中未找到该证书</li>
        <li>响应使用根 CA 私钥进行 SM2 签名，确保结果不可伪造</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.ocsp-query h2 { margin-bottom: 0.25rem; }
.desc { color: #888; font-size: 0.9rem; margin-bottom: 1.5rem; }

.section {
  background: #fff; border-radius: 12px; padding: 1.5rem;
  margin-bottom: 1.25rem; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.section h3 { margin-bottom: 0.5rem; font-size: 1rem; }

.query-bar { display: flex; gap: 0.75rem; }
.serial-input {
  flex: 1; padding: 0.65rem 0.85rem; border: 1.5px solid #d0d0d0;
  border-radius: 8px; font-size: 0.95rem; font-family: monospace;
}
.serial-input:focus { border-color: #0f3460; outline: none; }

.btn { padding: 0.65rem 1.5rem; background: #1a1a2e; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 0.95rem; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.error { color: #c00; margin-top: 0.75rem; }

.result-header {
  display: flex; align-items: center; gap: 0.5rem; padding: 1rem;
  border-radius: 8px; margin-bottom: 1rem; font-size: 1.1rem; font-weight: 600;
}
.result-good { background: #d4edda; color: #155724; }
.result-revoked { background: #f8d7da; color: #721c24; }
.result-unknown { background: #fff3cd; color: #856404; }

.detail-grid {
  display: grid; grid-template-columns: 140px 1fr;
  gap: 0.4rem 1rem; font-size: 0.85rem;
}
.detail-grid dt { color: #666; font-weight: 600; }
.detail-grid dd { word-break: break-all; }
code { font-size: 0.8rem; background: #f0f0f0; padding: 0.15rem 0.35rem; border-radius: 4px; }
.sig { color: #888; }

.info ul { padding-left: 1.25rem; font-size: 0.85rem; color: #555; }
.info li { margin-bottom: 0.25rem; }
</style>
