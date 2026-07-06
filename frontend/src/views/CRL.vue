<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useCRLStore } from '@/stores/crl'
import { useCAStore } from '@/stores/ca'
import { useCertStore } from '@/stores/cert'

const crlStore = useCRLStore()
const caStore = useCAStore()
const certStore = useCertStore()

const loading = ref(false)
const error = ref('')
const success = ref('')

const revokeForm = ref({
  cert_serial_number: '',
  reason: 'unspecified',
})

onMounted(async () => {
  await caStore.fetchStatus()
  await Promise.all([crlStore.fetchCurrent(), certStore.fetchList()])
})

async function handleRevoke() {
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    const res = await crlStore.revoke(revokeForm.value)
    const revokeRes = res as { cert_serial_number?: string }
    success.value = `Revoked: ${revokeRes.cert_serial_number?.slice(0, 20)}...`
    revokeForm.value.cert_serial_number = ''
    await certStore.fetchList()
    await crlStore.fetchCurrent()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Revoke failed'
  } finally {
    loading.value = false
  }
}

async function handleGenerate() {
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    const genRes = await crlStore.generate() as { crl_number?: number; revoked_count?: number }
    success.value = `CRL #${genRes.crl_number} generated with ${genRes.revoked_count} revocations`
    await crlStore.fetchCurrent()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'CRL generation failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="crl">
    <h2>证书撤销列表 (CRL)</h2>

    <!-- 撤销表单 -->
    <section class="section" v-if="caStore.initialized">
      <h3>撤销证书</h3>
      <form @submit.prevent="handleRevoke" class="form-row">
        <label>
          证书序列号
          <input v-model="revokeForm.cert_serial_number" required placeholder="输入证书序列号..." />
        </label>
        <label>
          撤销原因
          <select v-model="revokeForm.reason">
            <option value="unspecified">未指定</option>
            <option value="keyCompromise">密钥泄露</option>
            <option value="affiliationChanged">隶属关系变更</option>
            <option value="superseded">已被取代</option>
            <option value="cessationOfOperation">停止运营</option>
          </select>
        </label>
        <button type="submit" :disabled="loading">{{ loading ? '...' : '撤销' }}</button>
      </form>
    </section>

    <!-- 生成 CRL -->
    <section class="section" v-if="caStore.initialized">
      <h3>生成 CRL</h3>
      <p class="desc">生成由根 CA 签名的 CRL，包含所有待处理的撤销记录。</p>
      <button @click="handleGenerate" :disabled="loading">
        {{ loading ? '生成中...' : '生成 CRL' }}
      </button>
    </section>

    <!-- 消息 -->
    <p v-if="success" class="ok">{{ success }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <!-- 当前 CRL -->
    <section class="section">
      <h3>当前 CRL</h3>
      <div v-if="crlStore.currentCRL?.crl_number">
        <div class="crl-meta">
          <div><strong>CRL #</strong> {{ crlStore.currentCRL.crl_number }}</div>
          <div><strong>签发者</strong> {{ crlStore.currentCRL.issuer_dn }}</div>
          <div><strong>本次更新</strong> {{ new Date(crlStore.currentCRL.this_update).toLocaleString() }}</div>
          <div><strong>下次更新</strong> {{ new Date(crlStore.currentCRL.next_update).toLocaleString() }}</div>
          <div><strong>撤销数量</strong> {{ crlStore.currentCRL.revoked_count }}</div>
        </div>

        <!-- 撤销列表 -->
        <table v-if="crlStore.currentCRL.revoked_certificates?.length" style="margin-top:1rem">
          <thead>
            <tr>
              <th>序列号</th>
              <th>撤销原因</th>
              <th>撤销时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, idx) in crlStore.currentCRL.revoked_certificates" :key="idx">
              <td><code>{{ r.cert_serial_number?.slice(0, 20) }}...</code></td>
              <td>{{ r.reason }}</td>
              <td>{{ new Date(r.revoked_at).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="empty">暂无 CRL 发布记录。</p>
    </section>
  </div>
</template>

<style scoped>
.crl h2 {
  margin-bottom: 1.5rem;
}
.section {
  background: #fff;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1.25rem;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
.section h3 {
  margin-bottom: 1rem;
  font-size: 1.1rem;
}
.desc {
  color: #666;
  margin-bottom: 0.75rem;
  font-size: 0.9rem;
}
.form-row {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  flex-wrap: wrap;
}
label {
  display: flex;
  flex-direction: column;
  font-size: 0.85rem;
  color: #555;
  gap: 0.3rem;
  flex: 1;
  min-width: 180px;
}
input,
select {
  padding: 0.5rem 0.75rem;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  font-size: 0.9rem;
}
button {
  padding: 0.55rem 1.5rem;
  background: #1a1a2e;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.95rem;
}
button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.ok {
  color: #155724;
  background: #d4edda;
  padding: 0.5rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}
.error {
  color: #721c24;
  background: #f8d7da;
  padding: 0.5rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}
.crl-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.5rem;
  font-size: 0.9rem;
}
.crl-meta strong {
  color: #555;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: 0.5rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid #eee;
  font-size: 0.85rem;
}
th {
  color: #666;
  font-weight: 600;
}
code {
  font-size: 0.8rem;
  background: #f0f0f0;
  padding: 0.15rem 0.35rem;
  border-radius: 4px;
}
.empty {
  color: #888;
  font-style: italic;
}
</style>
