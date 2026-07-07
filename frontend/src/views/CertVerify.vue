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
  valid?: boolean; details?: string; cert_subject?: string
  issuer_subject?: string; serial_number?: string
  not_before?: string; not_after?: string; in_validity_period?: boolean
} | null>(null)

const crlResult = ref<{
  revoked?: boolean; reason?: string; revocation_date?: string; error?: string
} | null>(null)

async function verifySignature() {
  if (!certPem.value.trim() || !issuerCertPem.value.trim()) {
    toast.error('请填写证书和上级证书 PEM')
    return
  }
  loading.value = true; signResult.value = null
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
  loading.value = true; crlResult.value = null
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

// 综合验证：加载CRL + 签名验证 + 撤销验证
async function verifyAll() {
  if (!certPem.value.trim()) {
    toast.error('请先粘贴待验证的证书 PEM')
    return
  }
  loading.value = true
  signResult.value = null
  crlResult.value = null
  try {
    // 1. 加载当前 CRL
    if (!crlPem.value.trim()) {
      const data = await crlApi.current()
      if ('crl_pem' in data) {
        crlPem.value = data.crl_pem
      }
    }
    // 2. 签名验证（需要签发者证书）
    if (issuerCertPem.value.trim()) {
      signResult.value = await certApi.verify(certPem.value, issuerCertPem.value)
    }
    // 3. CRL 撤销验证
    if (crlPem.value.trim()) {
      crlResult.value = await certApi.verifyRevocation(certPem.value, crlPem.value)
    }
    if (signResult.value || crlResult.value) {
      toast.success('综合验证完成')
    } else {
      toast.error('未执行任何验证，请填写签发者证书或加载CRL')
    }
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="cert-verify">
    <h2>证书验证工具</h2>

    <!-- 证书输入 -->
    <section class="section">
      <h3>证书 PEM</h3>
      <textarea v-model="certPem" rows="5" placeholder="粘贴待验证的证书 PEM（-----BEGIN CERTIFICATE----- ...）"></textarea>
      <div style="margin-top:0.75rem;display:flex;gap:0.5rem;flex-wrap:wrap">
        <button class="btn btn-primary" @click="verifyAll" :disabled="loading">
          {{ loading ? '⏳ 验证中...' : '🔍 综合验证（签名+撤销）' }}
        </button>
      </div>
    </section>

    <!-- 签名链验证 -->
    <section class="section">
      <h3>签名链验证</h3>
      <textarea v-model="issuerCertPem" rows="4" placeholder="粘贴上级/根证书 PEM..."></textarea>
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
.warn { color: #856404; }
</style>
