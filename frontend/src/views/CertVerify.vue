<script setup lang="ts">
import { ref } from 'vue'

defineOptions({ name: 'CertVerifyPage' })

const certPem = ref('')
const issuerCertPem = ref('')
const crlPem = ref('')
const loading = ref(false)
const error = ref('')

// 签名验证结果
const signResult = ref<{
  valid?: boolean; details?: string; cert_subject?: string
  issuer_subject?: string; serial_number?: string
  not_before?: string; not_after?: string; in_validity_period?: boolean
} | null>(null)

// 撤销验证结果
const crlResult = ref<{
  revoked?: boolean; reason?: string; revocation_date?: string; error?: string
} | null>(null)

async function verifySignature() {
  if (!certPem.value.trim() || !issuerCertPem.value.trim()) {
    error.value = '请填写证书和上级证书 PEM'
    return
  }
  loading.value = true; error.value = ''; signResult.value = null
  try {
    const res = await fetch('/api/cert/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('gm_pki_token')}` },
      body: JSON.stringify({ cert_pem: certPem.value, issuer_cert_pem: issuerCertPem.value }),
    })
    signResult.value = await res.json()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '验证失败'
  } finally {
    loading.value = false
  }
}

async function verifyRevocation() {
  if (!certPem.value.trim() || !crlPem.value.trim()) {
    error.value = '请填写证书和 CRL PEM'
    return
  }
  loading.value = true; error.value = ''; crlResult.value = null
  try {
    const res = await fetch('/api/cert/verify-revocation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('gm_pki_token')}` },
      body: JSON.stringify({ cert_pem: certPem.value, crl_pem: crlPem.value }),
    })
    crlResult.value = await res.json()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '验证失败'
  } finally {
    loading.value = false
  }
}

async function loadCurrentCRL() {
  try {
    const res = await fetch('/api/crl/download', {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('gm_pki_token')}` },
    })
    if (res.ok) {
      crlPem.value = await res.text()
    }
  } catch { /* ignore */ }
}
</script>

<template>
  <div class="cert-verify">
    <h2>证书验证工具</h2>

    <!-- 证书输入 -->
    <section class="section">
      <h3>证书 PEM</h3>
      <textarea v-model="certPem" rows="6" placeholder="粘贴待验证的证书 PEM（-----BEGIN CERTIFICATE----- ...）"></textarea>
    </section>

    <!-- 签名链验证 -->
    <section class="section">
      <h3>签名链验证</h3>
      <textarea v-model="issuerCertPem" rows="5" placeholder="粘贴上级/根证书 PEM..."></textarea>
      <button class="btn" @click="verifySignature" :disabled="loading" style="margin-top:0.75rem">
        {{ loading ? '验证中...' : '验证签名链' }}
      </button>
      <div v-if="signResult" class="result" :class="signResult.valid ? 'result-ok' : 'result-fail'">
        <p><strong>{{ signResult.valid ? '✅ 签名有效' : '❌ 签名无效' }}</strong> — {{ signResult.details }}</p>
        <dl v-if="signResult.cert_subject" class="iv">
          <dt>证书主题</dt><dd>{{ signResult.cert_subject }}</dd>
          <dt>签发者</dt><dd>{{ signResult.issuer_subject }}</dd>
          <dt>序列号</dt><dd><code>{{ signResult.serial_number }}</code></dd>
          <dt>有效期</dt><dd>{{ signResult.not_before }} ~ {{ signResult.not_after }}</dd>
          <dt>在有效期内</dt><dd>{{ signResult.in_validity_period ? '✅ 是' : '❌ 否' }}</dd>
        </dl>
      </div>
    </section>

    <!-- CRL 撤销验证 -->
    <section class="section">
      <h3>CRL 撤销验证</h3>
      <div class="iv-row">
        <textarea v-model="crlPem" rows="4" placeholder="粘贴 CRL PEM 或点击右侧按钮加载当前 CRL..."></textarea>
        <button class="btn btn-sm" @click="loadCurrentCRL">📥 加载当前 CRL</button>
      </div>
      <button class="btn" @click="verifyRevocation" :disabled="loading" style="margin-top:0.5rem">
        {{ loading ? '验证中...' : '验证撤销状态' }}
      </button>
      <div v-if="crlResult" class="result" :class="crlResult.revoked ? 'result-fail' : 'result-ok'">
        <p><strong>{{ crlResult.revoked ? '❌ 已被撤销' : '✅ 未被撤销' }}</strong></p>
        <p v-if="crlResult.revoked">撤销原因: {{ crlResult.reason }}</p>
        <p v-if="crlResult.revocation_date">撤销时间: {{ new Date(crlResult.revocation_date).toLocaleString() }}</p>
        <p v-if="crlResult.error" class="warn">{{ crlResult.error }}</p>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.cert-verify h2 { margin-bottom: 1.5rem; }
.section {
  background: #fff; border-radius: 12px; padding: 1.5rem;
  margin-bottom: 1.25rem; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.section h3 { margin-bottom: 0.75rem; font-size: 1.05rem; }
textarea {
  width: 100%; padding: 0.6rem 0.75rem; border: 1px solid #d0d0d0;
  border-radius: 6px; font-size: 0.8rem; font-family: monospace; resize: vertical;
}
.btn { padding: 0.6rem 1.5rem; background: #1a1a2e; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 0.95rem; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-sm { padding: 0.35rem 0.8rem; font-size: 0.82rem; }
.result { margin-top: 1rem; padding: 1rem; border-radius: 8px; }
.result-ok { background: #d4edda; color: #155724; }
.result-fail { background: #f8d7da; color: #721c24; }
.iv { margin-top: 0.5rem; display: grid; grid-template-columns: 100px 1fr; gap: 0.25rem 0.75rem; font-size: 0.85rem; }
.iv dt { color: #555; font-weight: 600; }
.iv-row { display: flex; gap: 0.75rem; align-items: flex-start; }
.iv-row textarea { flex: 1; }
.error { color: #c00; margin-top: 1rem; }
.warn { color: #856404; }
</style>
