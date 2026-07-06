<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useCertStore } from '@/stores/cert'
import { useCAStore } from '@/stores/ca'

const certStore = useCertStore()
const caStore = useCAStore()
const loading = ref(false)
const error = ref('')
const success = ref('')

const form = ref({
  user_name: '',
  email: '',
  organization: '',
  department: '',
  province: '',
  city: '',
  cert_type: 'sign',
  validity_days: 365,
  public_key_pem: '',
})

onMounted(() => {
  caStore.fetchStatus()
  certStore.fetchList()
})

async function handleIssue() {
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    const payload: Record<string, unknown> = { ...form.value }
    if (!payload.public_key_pem) delete payload.public_key_pem
    const res = await certStore.issue(payload)
    success.value = `Certificate issued! Serial: ${(res as any).serial_number?.slice(0, 20)}...`
    form.value.user_name = ''
    form.value.email = ''
  } catch (e: any) {
    error.value = e.message || 'Issue failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="user-cert">
    <h2>用户证书管理</h2>

    <!-- 签发表单 -->
    <section class="section" v-if="caStore.initialized">
      <h3>签发新证书</h3>
      <form @submit.prevent="handleIssue" class="form-grid">
        <label>
          用户名 *
          <input v-model="form.user_name" required maxlength="128" placeholder="如: 张三" />
        </label>
        <label>
          邮箱
          <input v-model="form.email" type="email" maxlength="255" />
        </label>
        <label>
          组织
          <input v-model="form.organization" maxlength="255" />
        </label>
        <label>
          部门
          <input v-model="form.department" maxlength="255" />
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
          证书类型
          <select v-model="form.cert_type">
            <option value="sign">签名证书</option>
            <option value="encrypt">加密证书</option>
          </select>
        </label>
        <label>
          有效期（天）
          <input v-model.number="form.validity_days" type="number" min="1" max="36500" />
        </label>
        <label class="full-width">
          公钥 PEM（可选 — 导入已有公钥）
          <textarea
            v-model="form.public_key_pem"
            rows="3"
            placeholder="粘贴 PEM 编码的公钥以导入..."
          ></textarea>
        </label>
        <div class="form-actions">
          <button type="submit" :disabled="loading || !form.user_name">
            {{ loading ? '签发中...' : '签发证书' }}
          </button>
        </div>
      </form>
      <p v-if="success" class="ok">{{ success }}</p>
      <p v-if="error" class="error">{{ error }}</p>
    </section>
    <section class="section" v-else>
      <p class="warn">⚠️ 请先初始化 CA。</p>
    </section>

    <!-- 证书列表 -->
    <section class="section">
      <h3>已签发证书</h3>
      <table v-if="certStore.certs.length">
        <thead>
          <tr>
            <th>序列号</th>
            <th>类型</th>
            <th>主题 DN</th>
            <th>用户</th>
            <th>到期日期</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in certStore.certs" :key="c.id">
            <td><code>{{ c.serial_number?.slice(0, 14) }}...</code></td>
            <td>
              <span class="badge" :class="c.cert_type === 'sign' ? 'badge-blue' : 'badge-purple'">
                {{ c.cert_type }}
              </span>
            </td>
            <td>{{ c.subject_dn }}</td>
            <td>{{ c.user_name }}</td>
            <td>{{ new Date(c.not_after).toLocaleDateString() }}</td>
            <td>
              <span :class="['badge', c.status === 'active' ? 'badge-green' : 'badge-red']">
                {{ c.status }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty">暂无已签发证书。</p>
    </section>
  </div>
</template>

<style scoped>
.user-cert h2 {
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
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}
.full-width {
  grid-column: 1 / -1;
}
label {
  display: flex;
  flex-direction: column;
  font-size: 0.85rem;
  color: #555;
  gap: 0.3rem;
}
input,
select,
textarea {
  padding: 0.5rem 0.75rem;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  font-size: 0.9rem;
}
textarea {
  resize: vertical;
  font-family: monospace;
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
.ok {
  color: #155724;
  margin-top: 0.75rem;
}
.warn {
  color: #856404;
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
.badge-red {
  background: #f8d7da;
  color: #721c24;
}
.badge-blue {
  background: #d1ecf1;
  color: #0c5460;
}
.badge-purple {
  background: #e2d9f3;
  color: #5a3d7a;
}
.empty {
  color: #888;
  font-style: italic;
}
</style>
