<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useCAStore } from '@/stores/ca'
import { caApi } from '@/api'

const caStore = useCAStore()
const loading = ref(false)
const error = ref('')
const success = ref('')

const form = ref({
  ca_name: 'GM-PKI-CA',
  organization: 'Default Org',
  country: 'CN',
  province: '',
  city: '',
  signature_algorithm: 'SM3WITHSM2',
  validity_days: 3650,
})

// 证书详情
const selectedCert = ref<Record<string, unknown> | null>(null)
const detailLoading = ref(false)
const pemCopied = ref(false)

onMounted(() => {
  caStore.fetchStatus()
  caStore.fetchRootCerts()
})

async function handleInit() {
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    const res = await caStore.initialize(form.value)
    await caStore.fetchRootCerts()
    success.value = `根 CA 签发成功！序列号: ${(res as { serial_number?: string }).serial_number?.slice(0, 20)}...`
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Initialization failed'
  } finally {
    loading.value = false
  }
}

async function showDetail(serial: string) {
  detailLoading.value = true
  try {
    selectedCert.value = await caApi.getRootCert(serial)
  } catch {
    selectedCert.value = null
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  selectedCert.value = null
}

async function copyPEM(pem: string) {
  try {
    await navigator.clipboard.writeText(pem)
    pemCopied.value = true
    setTimeout(() => { pemCopied.value = false }, 2000)
  } catch {
    // fallback for older browsers
    const ta = document.createElement('textarea')
    ta.value = pem
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    pemCopied.value = true
    setTimeout(() => { pemCopied.value = false }, 2000)
  }
}

async function handleDownload(serial: string) {
  try {
    await caApi.downloadRootCert(serial)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '下载失败'
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

    <!-- 成功消息 -->
    <p v-if="success" class="success-msg">{{ success }}</p>

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
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in caStore.rootCerts"
            :key="c.id"
            @click="showDetail(c.serial_number)"
            class="clickable-row"
            :class="{ 'row-selected': selectedCert?.serial_number === c.serial_number }"
          >
            <td><code>{{ c.serial_number?.slice(0, 16) }}...</code></td>
            <td>{{ c.subject_dn }}</td>
            <td>{{ c.signature_algorithm }}</td>
            <td>{{ new Date(c.not_before).toLocaleDateString() }}</td>
            <td>{{ new Date(c.not_after).toLocaleDateString() }}</td>
            <td><span class="badge badge-green">{{ c.status }}</span></td>
            <td>
              <button class="btn-sm" @click.stop="handleDownload(c.serial_number)">⬇ 下载</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty">暂无根证书。</p>
    </section>

    <!-- 证书详情面板 -->
    <section class="section" v-if="selectedCert">
      <div class="detail-header">
        <h3>证书详情</h3>
        <button class="btn-close" @click="closeDetail">✕</button>
      </div>
      <div v-if="detailLoading" class="loading">加载中...</div>
      <dl v-else class="detail-grid">
        <dt>序列号</dt>
        <dd><code>{{ selectedCert.serial_number }}</code></dd>
        <dt>主题 DN</dt>
        <dd>{{ selectedCert.subject_dn }}</dd>
        <dt>签发者 DN</dt>
        <dd>{{ selectedCert.issuer_dn }}</dd>
        <dt>签名算法</dt>
        <dd>{{ selectedCert.signature_algorithm }}</dd>
        <dt>密钥长度</dt>
        <dd>{{ selectedCert.key_size }} bit</dd>
        <dt>生效时间</dt>
        <dd>{{ selectedCert.not_before }}</dd>
        <dt>到期时间</dt>
        <dd>{{ selectedCert.not_after }}</dd>
        <dt>状态</dt>
        <dd><span :class="['badge', selectedCert.status === 'active' ? 'badge-green' : 'badge-red']">{{ selectedCert.status }}</span></dd>
        <dt>主题密钥标识符</dt>
        <dd><code>{{ selectedCert.subject_key_identifier || '—' }}</code></dd>
        <dt>授权密钥标识符</dt>
        <dd><code>{{ selectedCert.authority_key_identifier || '—' }}</code></dd>
        <dt>基本约束</dt>
        <dd>{{ selectedCert.basic_constraints || '—' }}</dd>
        <dt>密钥用途</dt>
        <dd>{{ selectedCert.key_usage || '—' }}</dd>
        <dt>证书 PEM</dt>
        <dd>
          <pre class="pem-preview">{{ (selectedCert.cert_pem as string)?.slice(0, 300) }}...</pre>
          <button class="btn-copy" @click="copyPEM(selectedCert.cert_pem as string)">
            {{ pemCopied ? '✅ 已复制' : '📋 复制 PEM' }}
          </button>
        </dd>
      </dl>
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
.ok { color: #155724; }
.warn { color: #856404; }
.loading { color: #888; font-style: italic; }

.success-msg {
  background: #d4edda;
  color: #155724;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
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
.btn-sm {
  padding: 0.3rem 0.7rem;
  font-size: 0.8rem;
  background: #555;
}
.error {
  color: #c00;
  margin-top: 0.75rem;
}

/* 表格 */
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  padding: 0.5rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid #eee;
  font-size: 0.85rem;
}
th { color: #666; font-weight: 600; }
.clickable-row {
  cursor: pointer;
  transition: background 0.15s;
}
.clickable-row:hover {
  background: #f8f9fa;
}
.row-selected {
  background: #e8f0fe;
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
.badge-green { background: #d4edda; color: #155724; }
.badge-red { background: #f8d7da; color: #721c24; }
.empty { color: #888; font-style: italic; }

/* 详情面板 */
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.detail-header h3 { margin-bottom: 0; }
.btn-close {
  background: none;
  color: #888;
  font-size: 1.1rem;
  padding: 0.25rem 0.5rem;
}
.btn-close:hover { color: #333; }

.detail-grid {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 0.5rem 1rem;
  font-size: 0.85rem;
}
.detail-grid dt {
  color: #666;
  font-weight: 600;
}
.detail-grid dd {
  word-break: break-all;
}

.pem-preview {
  background: #f8f8f8;
  padding: 0.5rem;
  border-radius: 6px;
  font-size: 0.72rem;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 120px;
  overflow-y: auto;
  margin-bottom: 0.4rem;
}
.btn-copy {
  padding: 0.3rem 0.7rem;
  font-size: 0.78rem;
  background: transparent;
  color: #0f3460;
  border: 1px solid #0f3460;
  border-radius: 6px;
  cursor: pointer;
}
.btn-copy:hover { background: rgba(15, 52, 96, 0.06); }
</style>
