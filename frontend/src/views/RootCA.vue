<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useCAStore } from '@/stores/ca'

const caStore = useCAStore()
const loading = ref(false)
const error = ref('')

const form = ref({
  ca_name: 'GM-PKI-CA',
  organization: 'Default Org',
  country: 'CN',
  province: '',
  city: '',
  signature_algorithm: 'SM3WITHSM2',
  validity_days: 3650,
})

onMounted(() => {
  caStore.fetchStatus()
  caStore.fetchRootCerts()
})

async function handleInit() {
  loading.value = true
  error.value = ''
  try {
    await caStore.initialize(form.value)
    await caStore.fetchRootCerts()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Initialization failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="root-ca">
    <h2>根 CA 管理</h2>

    <!-- CA 状态 -->
    <section class="section">
      <h3>CA 状态</h3>
      <p v-if="caStore.initialized" class="ok">✅ CA 已初始化 — {{ caStore.caName }}</p>
      <p v-else class="warn">⚠️ CA 尚未初始化，请使用下方表单进行初始化。</p>
    </section>

    <!-- 初始化表单 -->
    <section class="section" v-if="!caStore.initialized">
      <h3>初始化 CA</h3>
      <form @submit.prevent="handleInit" class="form-grid">
        <label>
          CA 名称
          <input v-model="form.ca_name" required maxlength="255" />
        </label>
        <label>
          组织
          <input v-model="form.organization" required maxlength="255" />
        </label>
        <label>
          国家
          <input v-model="form.country" required maxlength="2" />
        </label>
        <label>
          省份
          <input v-model="form.province" maxlength="128" />
        </label>
        <label>
          城市
          <input v-model="form.city" maxlength="128" />
        </label>
        <label>
          签名算法
          <select v-model="form.signature_algorithm">
            <option>SM3WITHSM2</option>
            <option>SHA256WITHRSA</option>
          </select>
        </label>
        <label>
          有效期（天）
          <input v-model.number="form.validity_days" type="number" min="1" max="36500" />
        </label>
        <div class="form-actions">
          <button type="submit" :disabled="loading">
            {{ loading ? '初始化中...' : '初始化 CA' }}
          </button>
        </div>
      </form>
      <p v-if="error" class="error">{{ error }}</p>
    </section>

    <!-- 根证书列表 -->
    <section class="section">
      <h3>根证书列表</h3>
      <table v-if="caStore.rootCerts.length">
        <thead>
          <tr>
            <th>序列号</th>
            <th>主题 DN</th>
            <th>算法</th>
            <th>生效日期</th>
            <th>到期日期</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in caStore.rootCerts" :key="c.id">
            <td><code>{{ c.serial_number?.slice(0, 16) }}...</code></td>
            <td>{{ c.subject_dn }}</td>
            <td>{{ c.signature_algorithm }}</td>
            <td>{{ new Date(c.not_before).toLocaleDateString() }}</td>
            <td>{{ new Date(c.not_after).toLocaleDateString() }}</td>
            <td><span class="badge badge-green">{{ c.status }}</span></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty">暂无根证书。</p>
    </section>
  </div>
</template>

<style scoped>
.root-ca h2 {
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
.ok {
  color: #155724;
}
.warn {
  color: #856404;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}
label {
  display: flex;
  flex-direction: column;
  font-size: 0.85rem;
  color: #555;
  gap: 0.3rem;
}
input,
select {
  padding: 0.5rem 0.75rem;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  font-size: 0.9rem;
}
.form-actions {
  grid-column: 1 / -1;
}
button {
  padding: 0.6rem 1.5rem;
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
.error {
  color: #c00;
  margin-top: 0.75rem;
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
.badge {
  padding: 0.15rem 0.6rem;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 600;
}
.badge-green {
  background: #d4edda;
  color: #155724;
}
.empty {
  color: #888;
  font-style: italic;
}
</style>
