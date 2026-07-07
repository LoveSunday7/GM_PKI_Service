<script setup lang="ts">
import { ref } from 'vue'
import { certApi, crlApi } from '@/api'
import { useToast } from '@/composables/useToast'
import { formatError } from '@/utils/errors'

defineOptions({ name: 'CertVerifyPage' })

const toast = useToast()
const certPem = ref('')
const issuerCertPem = ref('')
const crlPem = ref('')
const loading = ref(false)

const signResult = ref<{
  valid?: boolean
  details?: string
  cert_subject?: string
  issuer_subject?: string
  serial_number?: string
  not_before?: string
  not_after?: string
  in_validity_period?: boolean
} | null>(null)

const crlResult = ref<{
  revoked?: boolean
  reason?: string | null
  revocation_date?: string | null
  error?: string
} | null>(null)

async function verifySignature() {
  if (!certPem.value.trim() || !issuerCertPem.value.trim()) {
    toast.error('请填写证书和上级证书 PEM')
    return
  }
  loading.value = true
  signResult.value = null
  try {
    signResult.value = await certApi.verify(certPem.value, issuerCertPem.value)
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    loading.value = false
  }
}

async function verifyRevocation() {
  if (!certPem.value.trim() || !crlPem.value.trim()) {
    toast.error('请填写证书和 CRL PEM')
    return
  }
  loading.value = true
  crlResult.value = null
  try {
    crlResult.value = await certApi.verifyRevocation(certPem.value, crlPem.value)
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    loading.value = false
  }
}

async function loadCurrentCRL() {
  try {
    const data = await crlApi.current()
    if ('crl_pem' in data) {
      crlPem.value = data.crl_pem
      toast.success('CRL 加载成功')
    } else {
      toast.error('暂无 CRL 数据')
    }
  } catch (e: unknown) {
    toast.error(formatError(e))
  }
}

async function verifyAll() {
  if (!certPem.value.trim()) {
    toast.error('请先粘贴待验证的证书 PEM')
    return
  }
  loading.value = true
  signResult.value = null
  crlResult.value = null
  try {
    if (issuerCertPem.value.trim()) {
      signResult.value = await certApi.verify(certPem.value, issuerCertPem.value)
    }
    if (!crlPem.value.trim()) {
      const data = await crlApi.current()
      if ('crl_pem' in data) crlPem.value = data.crl_pem
    }
    if (crlPem.value.trim()) {
      crlResult.value = await certApi.verifyRevocation(certPem.value, crlPem.value)
    }
    toast.success('验证完成')
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="cert-verify">
    <h2>证书验证</h2>

    <section class="section">
      <h3>待验证证书 PEM</h3>
      <textarea v-model="certPem" rows="6" placeholder="-----BEGIN CERTIFICATE-----"></textarea>
      <button class="btn btn-primary" :disabled="loading" @click="verifyAll">
        {{ loading ? '验证中...' : '综合验证' }}
      </button>
    </section>

    <section class="section">
      <h3>证书链验证</h3>
      <textarea v-model="issuerCertPem" rows="5" placeholder="粘贴上级/根证书 PEM"></textarea>
      <button class="btn" :disabled="loading" @click="verifySignature">验证证书链</button>
      <div v-if="signResult" class="result" :class="signResult.valid ? 'result-ok' : 'result-fail'">
        <p><strong>{{ signResult.valid ? '证书链有效' : '证书链无效' }}</strong>：{{ signResult.details }}</p>
        <dl v-if="signResult.cert_subject" class="iv">
          <dt>证书主题</dt><dd>{{ signResult.cert_subject }}</dd>
          <dt>签发者</dt><dd>{{ signResult.issuer_subject }}</dd>
          <dt>序列号</dt><dd><code>{{ signResult.serial_number }}</code></dd>
          <dt>有效期</dt><dd>{{ signResult.not_before }} 至 {{ signResult.not_after }}</dd>
          <dt>当前有效</dt><dd>{{ signResult.in_validity_period ? '是' : '否' }}</dd>
        </dl>
      </div>
    </section>

    <section class="section">
      <h3>CRL 撤销验证</h3>
      <div class="iv-row">
        <textarea v-model="crlPem" rows="5" placeholder="粘贴 CRL PEM，或加载当前 CRL"></textarea>
        <button class="btn btn-sm" @click="loadCurrentCRL">加载当前 CRL</button>
      </div>
      <button class="btn" :disabled="loading" @click="verifyRevocation">验证撤销状态</button>
      <div v-if="crlResult" class="result" :class="crlResult.revoked ? 'result-fail' : 'result-ok'">
        <p><strong>{{ crlResult.revoked ? '已被撤销' : '未被撤销' }}</strong></p>
        <p v-if="crlResult.reason">原因: {{ crlResult.reason }}</p>
        <p v-if="crlResult.revocation_date">撤销时间: {{ new Date(crlResult.revocation_date).toLocaleString() }}</p>
        <p v-if="crlResult.error" class="warn">{{ crlResult.error }}</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.cert-verify h2 { margin-bottom: 1.5rem; }
.section { background: #fff; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.25rem; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.section h3 { margin-bottom: 0.75rem; font-size: 1.05rem; }
textarea { width: 100%; padding: 0.6rem 0.75rem; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 0.8rem; font-family: monospace; resize: vertical; margin-bottom: 0.75rem; }
.btn { padding: 0.55rem 1.2rem; background: #1a1a2e; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: #0f3460; }
.btn-sm { padding: 0.4rem 0.75rem; font-size: 0.82rem; white-space: nowrap; }
.result { margin-top: 1rem; padding: 1rem; border-radius: 8px; }
.result-ok { background: #d4edda; color: #155724; }
.result-fail { background: #f8d7da; color: #721c24; }
.iv { margin-top: 0.5rem; display: grid; grid-template-columns: 100px 1fr; gap: 0.25rem 0.75rem; font-size: 0.85rem; }
.iv dt { color: #555; font-weight: 600; }
.iv dd { word-break: break-all; }
.iv-row { display: flex; gap: 0.75rem; align-items: flex-start; }
.iv-row textarea { flex: 1; }
.warn { color: #856404; }
</style>
