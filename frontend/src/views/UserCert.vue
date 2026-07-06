<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useCertStore } from '@/stores/cert'
import { useCAStore } from '@/stores/ca'
import { certApi, crlApi } from '@/api'
import { useToast } from '@/composables/useToast'
import { formatError } from '@/utils/errors'

const toast = useToast()
const certStore = useCertStore()
const caStore = useCAStore()
const loading = ref(false)
const certLoading = ref(true)

// ── 批量撤销 ───────────────────────────────────────────────────
const selectedSerials = ref<Set<string>>(new Set())
const batchRevoking = ref(false)

const activeFilteredCerts = computed(() =>
  certStore.certs.filter((c: { status: string }) => c.status === 'active')
)

function toggleSelect(serial: string) {
  const s = new Set(selectedSerials.value)
  if (s.has(serial)) s.delete(serial)
  else s.add(serial)
  selectedSerials.value = s
}

function toggleSelectAll() {
  if (selectedSerials.value.size === activeFilteredCerts.value.length) {
    selectedSerials.value = new Set()
  } else {
    selectedSerials.value = new Set(activeFilteredCerts.value.map((c: { serial_number: string }) => c.serial_number))
  }
}

async function handleBatchRevoke() {
  if (selectedSerials.value.size === 0) return
  batchRevoking.value = true
  let done = 0
  let failed = 0
  for (const serial of selectedSerials.value) {
    try {
      await crlApi.revoke({ cert_serial_number: serial, reason: 'unspecified' })
      done++
    } catch {
      failed++
    }
  }
  selectedSerials.value = new Set()
  loadCerts(1)
  batchRevoking.value = false
  if (failed) {
    toast.error(`撤销完成：${done} 张成功，${failed} 张失败`)
  } else {
    toast.success(`已成功撤销 ${done} 张证书`)
  }
}

// ── 筛选 + 分页 ────────────────────────────────────────────────
const filterType = ref('')
const filterStatus = ref('')
const PAGE_SIZE = 20

const totalPages = computed(() => Math.max(1, Math.ceil(certStore.total / certStore.pageSize)))

function loadCerts(page = 1) {
  certLoading.value = true
  const p: Record<string, unknown> = { page, page_size: PAGE_SIZE }
  if (filterType.value) p.cert_type = filterType.value
  if (filterStatus.value) p.status = filterStatus.value
  certStore.fetchList(p as { page?: number; page_size?: number; cert_type?: string; status?: string }).finally(() => { certLoading.value = false })
}

function onFilterChange() {
  loadCerts(1)
}

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

// 详情面板
const selectedCert = ref<Record<string, unknown> | null>(null)
const detailLoading = ref(false)
const copiedField = ref('')
// 状态查询结果
const certStatus = ref<{ status?: string; revoked_at?: string; reason?: string } | null>(null)

onMounted(async () => {
  await caStore.fetchStatus()
  loadCerts()
})

async function handleIssue() {
  loading.value = true
  try {
    const payload: Record<string, unknown> = { ...form.value }
    if (!payload.public_key_pem) delete payload.public_key_pem
    const res = await certStore.issue(payload)
    const issueRes = res as { serial_number?: string }
    toast.success(`签发成功！序列号: ${issueRes.serial_number?.slice(0, 20)}...`)
    loadCerts(1)
    form.value.user_name = ''
    form.value.email = ''
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    loading.value = false
  }
}

async function showDetail(serial: string) {
  detailLoading.value = true
  selectedCert.value = null
  certStatus.value = null
  try {
    selectedCert.value = await certApi.detail(serial)
    certStatus.value = await certApi.status(serial)
  } catch {
    selectedCert.value = null
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  selectedCert.value = null
  certStatus.value = null
}

async function handleDownload(serial: string) {
  try {
    await certApi.download(serial)
  } catch (e: unknown) {
    toast.error(formatError(e))
  }
}

async function copyText(text: string, field: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  copiedField.value = field
  setTimeout(() => { copiedField.value = '' }, 2000)
}
</script>

<template>
  <div class="user-cert">
    <h2>用户证书管理</h2>

    <!-- 签发表单 -->
    <section class="section" v-if="caStore.initialized">
      <h3>签发新证书</h3>
      <form @submit.prevent="handleIssue" class="form-grid">
        <label>用户名 *<input v-model="form.user_name" required maxlength="128" placeholder="如: 张三" /></label>
        <label>邮箱<input v-model="form.email" type="email" maxlength="255" /></label>
        <label>组织<input v-model="form.organization" maxlength="255" /></label>
        <label>部门<input v-model="form.department" maxlength="255" /></label>
        <label>省份<input v-model="form.province" maxlength="128" /></label>
        <label>城市<input v-model="form.city" maxlength="128" /></label>
        <label>证书类型
          <select v-model="form.cert_type">
            <option value="sign">签名证书</option>
            <option value="encrypt">加密证书</option>
          </select>
        </label>
        <label>有效期（天）<input v-model.number="form.validity_days" type="number" min="1" max="36500" /></label>
        <label class="full-width">公钥 PEM（可选）
          <textarea v-model="form.public_key_pem" rows="3" placeholder="粘贴 PEM 编码的公钥以导入..."></textarea>
        </label>
        <div class="form-actions">
          <button type="submit" :disabled="loading || !form.user_name">
            {{ loading ? '签发中...' : '签发证书' }}
          </button>
        </div>
      </form>
    </section>
    <section class="section" v-else>
      <p class="warn">⚠️ 请先初始化 CA。</p>
    </section>

    <!-- 证书列表 -->
    <section class="section">
      <h3>已签发证书</h3>

      <!-- 筛选栏 -->
      <div class="filter-bar" v-if="certStore.certs.length">
        <label class="filter-label">
          类型
          <select v-model="filterType" @change="onFilterChange()">
            <option value="">全部</option>
            <option value="sign">签名证书</option>
            <option value="encrypt">加密证书</option>
          </select>
        </label>
        <label class="filter-label">
          状态
          <select v-model="filterStatus" @change="onFilterChange()">
            <option value="">全部</option>
            <option value="active">有效</option>
            <option value="revoked">已撤销</option>
          </select>
        </label>
        <span class="filter-count">第 {{ certStore.page }} 页，共 {{ certStore.total }} 张</span>
      </div>

      <!-- 批量操作栏 -->
      <div class="batch-bar" v-if="selectedSerials.size > 0">
        <span>已选 <strong>{{ selectedSerials.size }}</strong> 张证书</span>
        <button class="btn btn-sm btn-danger" :disabled="batchRevoking" @click="handleBatchRevoke">
          {{ batchRevoking ? '⏳ 撤销中...' : `🚫 撤销所选 (${selectedSerials.size})` }}
        </button>
        <button class="btn btn-sm btn-ghost" @click="selectedSerials = new Set()">取消选择</button>
      </div>

      <template v-if="certStore.certs.length">
      <div class="responsive-table">
      <table>
        <thead>
          <tr>
            <th class="col-cb">
              <input type="checkbox" :checked="selectedSerials.size === activeFilteredCerts.length && activeFilteredCerts.length > 0" @click.stop="toggleSelectAll" />
            </th>
            <th>序列号</th>
            <th>类型</th>
            <th>主题 DN</th>
            <th>用户</th>
            <th>到期日期</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in certStore.certs"
            :key="c.id"
            :class="{ 'row-selected': selectedCert?.serial_number === c.serial_number }"
          >
            <td class="col-cb" data-label="">
              <input
                v-if="c.status === 'active'"
                type="checkbox"
                :checked="selectedSerials.has(c.serial_number)"
                @click.stop
                @change="toggleSelect(c.serial_number)"
              />
            </td>
            <td data-label="序列号" @click="showDetail(c.serial_number)" class="clickable-cell"><code>{{ c.serial_number?.slice(0, 14) }}...</code></td>
            <td data-label="类型" @click="showDetail(c.serial_number)" class="clickable-cell">
              <span class="badge" :class="c.cert_type === 'sign' ? 'badge-blue' : 'badge-purple'">
                {{ c.cert_type }}
              </span>
            </td>
            <td data-label="主题 DN" @click="showDetail(c.serial_number)" class="clickable-cell">{{ c.subject_dn }}</td>
            <td data-label="用户" @click="showDetail(c.serial_number)" class="clickable-cell">{{ c.user_name }}</td>
            <td data-label="到期日期" @click="showDetail(c.serial_number)" class="clickable-cell">{{ new Date(c.not_after).toLocaleDateString() }}</td>
            <td data-label="状态" @click="showDetail(c.serial_number)" class="clickable-cell">
              <span :class="['badge', c.status === 'active' ? 'badge-green' : 'badge-red']">{{ c.status }}</span>
            </td>
            <td data-label="操作" class="actions">
              <button class="btn-sm" @click.stop="handleDownload(c.serial_number)">⬇ 下载</button>
            </td>
          </tr>
        </tbody>
      </table>
      </div>

      <!-- 分页 -->
      <div class="pager" v-if="totalPages > 1">
        <button :disabled="certStore.page <= 1" @click="loadCerts(certStore.page - 1)">◀ 上一页</button>
        <template v-for="p in totalPages" :key="p">
          <button v-if="Math.abs(p - certStore.page) <= 2 || p === 1 || p === totalPages"
            :class="['page-btn', { active: p === certStore.page }]"
            @click="loadCerts(p)"
          >{{ p }}</button>
          <span v-else-if="Math.abs(p - certStore.page) === 3" class="page-dots">…</span>
        </template>
        <button :disabled="certStore.page >= totalPages" @click="loadCerts(certStore.page + 1)">下一页 ▶</button>
      </div>
      </template>
      <!-- 骨架屏 -->
      <div v-else-if="certLoading" class="skeleton-table">
        <div v-for="i in 4" :key="i" class="skeleton-row">
          <div class="skeleton skeleton-cell" style="width:12%" />
          <div class="skeleton skeleton-cell" style="width:8%" />
          <div class="skeleton skeleton-cell" style="width:30%" />
          <div class="skeleton skeleton-cell" style="width:10%" />
          <div class="skeleton skeleton-cell" style="width:12%" />
          <div class="skeleton skeleton-cell" style="width:8%" />
        </div>
      </div>
      <!-- 空状态 -->
      <div v-else class="empty-state">
        <div class="empty-icon">📜</div>
        <div class="empty-title">暂无已签发证书</div>
        <div class="empty-hint">请先初始化 CA，然后在上方填写信息签发第一张证书</div>
      </div>
    </section>

    <!-- 证书详情面板 -->
    <section class="section" v-if="selectedCert">
      <div class="detail-header">
        <h3>证书详情</h3>
        <button class="btn-close" @click="closeDetail">✕</button>
      </div>
      <div v-if="detailLoading" class="loading">加载中...</div>
      <template v-else>
        <div class="status-bar" v-if="certStatus">
          <span v-if="certStatus.status === 'active'" class="badge badge-green">● 有效</span>
          <span v-else class="badge badge-red">
            ● 已撤销<span v-if="certStatus.revoked_at"> — {{ new Date(certStatus.revoked_at).toLocaleString() }}</span>
            <span v-if="certStatus.reason"> ({{ certStatus.reason }})</span>
          </span>
        </div>
        <dl class="detail-grid">
          <dt>序列号</dt><dd><code>{{ selectedCert.serial_number }}</code></dd>
          <dt>证书类型</dt><dd>{{ selectedCert.cert_type === 'sign' ? '签名证书' : '加密证书' }}</dd>
          <dt>主题 DN</dt><dd>{{ selectedCert.subject_dn }}</dd>
          <dt>签发者 DN</dt><dd>{{ selectedCert.issuer_dn }}</dd>
          <dt>根证书序列号</dt><dd><code>{{ (selectedCert.root_cert_serial as string)?.slice(0, 20) }}...</code></dd>
          <dt>用户名</dt><dd>{{ selectedCert.user_name }}</dd>
          <dt>邮箱</dt><dd>{{ selectedCert.email || '—' }}</dd>
          <dt>组织</dt><dd>{{ selectedCert.organization || '—' }}</dd>
          <dt>部门</dt><dd>{{ selectedCert.department || '—' }}</dd>
          <dt>省份</dt><dd>{{ selectedCert.province || '—' }}</dd>
          <dt>城市</dt><dd>{{ selectedCert.city || '—' }}</dd>
          <dt>签名算法</dt><dd>{{ selectedCert.signature_algorithm }}</dd>
          <dt>生效时间</dt><dd>{{ selectedCert.not_before }}</dd>
          <dt>到期时间</dt><dd>{{ selectedCert.not_after }}</dd>
          <dt>密钥长度</dt><dd>{{ selectedCert.key_size }} bit</dd>
          <dt>证书 PEM</dt>
          <dd>
            <pre class="pem-preview">{{ (selectedCert.cert_pem as string)?.slice(0, 300) }}...</pre>
            <button class="btn-copy" @click="copyText(selectedCert.cert_pem as string, 'cert')">
              {{ copiedField === 'cert' ? '✅ 已复制' : '📋 复制 PEM' }}
            </button>
          </dd>
          <dt>公钥 PEM</dt>
          <dd v-if="selectedCert.public_key_pem">
            <pre class="pem-preview">{{ (selectedCert.public_key_pem as string)?.slice(0, 300) }}...</pre>
            <button class="btn-copy" @click="copyText(selectedCert.public_key_pem as string, 'pub')">
              {{ copiedField === 'pub' ? '✅ 已复制' : '📋 复制公钥' }}
            </button>
          </dd>
          <dd v-else>—</dd>
        </dl>
      </template>
    </section>
  </div>
</template>

<style scoped>
.user-cert h2 { margin-bottom: 1.5rem; }
.section {
  background: #fff; border-radius: 12px; padding: 1.5rem;
  margin-bottom: 1.25rem; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.section h3 { margin-bottom: 1rem; font-size: 1.1rem; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
.full-width { grid-column: 1 / -1; }
label { display: flex; flex-direction: column; font-size: 0.85rem; color: #555; gap: 0.3rem; }
input, select, textarea { padding: 0.5rem 0.75rem; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 0.9rem; }
textarea { resize: vertical; font-family: monospace; }
.form-actions { grid-column: 1 / -1; }

/* 筛选栏 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}
.filter-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.82rem;
  color: #666;
}
.filter-label select {
  padding: 0.35rem 0.5rem;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 0.85rem;
  background: #fff;
}
.filter-count {
  font-size: 0.8rem;
  color: #999;
  margin-left: auto;
}

/* 批量操作栏 */
.batch-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  margin-bottom: 0.5rem;
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 8px;
  font-size: 0.85rem;
}
.batch-bar .btn-sm { padding: 0.35rem 0.75rem; font-size: 0.8rem; border-radius: 6px; cursor: pointer; border: none; }
.batch-bar .btn-danger { background: #dc3545; color: #fff; }
.batch-bar .btn-danger:hover:not(:disabled) { background: #c82333; }
.batch-bar .btn-danger:disabled { opacity: 0.6; cursor: not-allowed; }
.batch-bar .btn-ghost { background: transparent; color: #666; border: 1px solid #ccc; }

/* 复选框列 */
.col-cb { width: 36px; text-align: center; }
.col-cb input[type="checkbox"] { cursor: pointer; width: 15px; height: 15px; }

/* 可点击的表格单元格 */
.clickable-cell { cursor: pointer; transition: background 0.15s; }
.clickable-cell:hover { background: #f8f9fa; }

/* 分页 */
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  margin-top: 0.75rem;
  flex-wrap: wrap;
}
.pager button {
  padding: 0.35rem 0.7rem;
  border: 1px solid #999;
  background: #fff;
  border-radius: 5px;
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 500;
  color: #333;
  min-width: 34px;
  transition: all 0.15s;
}
.pager button:disabled { opacity: 0.25; cursor: not-allowed; }
.pager button:hover:not(:disabled) { background: #0f3460; color: #fff; border-color: #0f3460; }
.pager .page-btn.active { background: #0f3460; color: #fff; border-color: #0f3460; font-weight: 700; }
.pager .page-dots { padding: 0 0.2rem; color: #666; font-weight: 500; }
button { padding: 0.6rem 1.5rem; background: #1a1a2e; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 0.95rem; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-sm { padding: 0.3rem 0.7rem; font-size: 0.8rem; background: #555; }
.ok { color: #155724; margin-top: 0.75rem; }
.warn { color: #856404; }
.error { color: #c00; margin-top: 0.75rem; }
.loading { color: #888; font-style: italic; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #eee; font-size: 0.85rem; }
th { color: #666; font-weight: 600; }
.row-selected { background: #e8f0fe; }
code { font-size: 0.8rem; background: #f0f0f0; padding: 0.15rem 0.35rem; border-radius: 4px; }
.badge { padding: 0.15rem 0.6rem; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
.badge-green { background: #d4edda; color: #155724; }
.badge-red { background: #f8d7da; color: #721c24; }
.badge-blue { background: #d1ecf1; color: #0c5460; }
.badge-purple { background: #e2d9f3; color: #5a3d7a; }
.empty { color: #888; font-style: italic; }

/* 详情面板 */
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.detail-header h3 { margin-bottom: 0; }
.btn-close { background: none; color: #888; font-size: 1.1rem; padding: 0.25rem 0.5rem; }
.btn-close:hover { color: #333; }
.status-bar { margin-bottom: 1rem; }
.detail-grid { display: grid; grid-template-columns: 140px 1fr; gap: 0.35rem 1rem; font-size: 0.85rem; }
.detail-grid dt { color: #666; font-weight: 600; }
.detail-grid dd { word-break: break-all; }
.pem-preview { background: #f8f8f8; padding: 0.5rem; border-radius: 6px; font-size: 0.72rem; font-family: monospace; white-space: pre-wrap; word-break: break-all; max-height: 100px; overflow-y: auto; margin-bottom: 0.4rem; }
.btn-copy { padding: 0.3rem 0.7rem; font-size: 0.78rem; background: transparent; color: #0f3460; border: 1px solid #0f3460; border-radius: 6px; cursor: pointer; }
.btn-copy:hover { background: rgba(15, 52, 96, 0.06); }
</style>
