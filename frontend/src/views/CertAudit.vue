<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { certApi, crlApi, type CertApplicationItem, type RevocationApplicationItem } from '@/api'
import { useToast } from '@/composables/useToast'
import { formatError } from '@/utils/errors'

defineOptions({ name: 'CertAuditPage' })

const toast = useToast()
const loading = ref(true)
const apps = ref<CertApplicationItem[]>([])
const revokeApps = ref<RevocationApplicationItem[]>([])
const total = ref(0)
const revokeTotal = ref(0)
const page = ref(1)
const filterStatus = ref('pending')
const approving = ref('')
const rejecting = ref('')
const selectedApp = ref<CertApplicationItem | null>(null)
const rejectForm = ref({ id: '', reason: '' })
const revokeApproving = ref('')
const revokeRejecting = ref('')
const revokeRejectForm = ref({ id: '', reason: '' })

function statusLabel(s: string) {
  if (s === 'pending') return '待审核'
  if (s === 'approved') return '已通过'
  if (s === 'rejected') return '已拒绝'
  return s
}

async function loadApps(p = 1) {
  loading.value = true
  try {
    const params: { status?: string; page?: number; page_size?: number } = { page: p, page_size: 20 }
    if (filterStatus.value) params.status = filterStatus.value
    const res = await certApi.applications(params)
    apps.value = res.items
    total.value = res.total
    page.value = res.page
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    loading.value = false
  }
}

onMounted(() => loadApps())

async function loadRevokeApps() {
  try {
    const res = await crlApi.revocationApplications({ status: filterStatus.value, page_size: 20 })
    revokeApps.value = res.items
    revokeTotal.value = res.total
  } catch (e: unknown) {
    toast.error(formatError(e))
  }
}

onMounted(loadRevokeApps)

async function handleApprove(id: string) {
  approving.value = id
  try {
    const res = await certApi.approve(id)
    toast.success(res.message)
    await loadApps(page.value)
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    approving.value = ''
  }
}

function openDetail(app: CertApplicationItem) {
  selectedApp.value = app
}

function openReject(id: string) {
  rejectForm.value = { id, reason: '' }
}

async function handleReject() {
  rejecting.value = rejectForm.value.id
  try {
    const res = await certApi.reject(rejectForm.value.id, rejectForm.value.reason)
    toast.success(res.message)
    rejectForm.value = { id: '', reason: '' }
    await loadApps(page.value)
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    rejecting.value = ''
  }
}

async function handleApproveRevocation(id: string) {
  revokeApproving.value = id
  try {
    const res = await crlApi.approveRevocation(id)
    toast.success(res.message)
    await loadRevokeApps()
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    revokeApproving.value = ''
  }
}

function openRevokeReject(id: string) {
  revokeRejectForm.value = { id, reason: '' }
}

async function handleRejectRevocation() {
  revokeRejecting.value = revokeRejectForm.value.id
  try {
    const res = await crlApi.rejectRevocation(revokeRejectForm.value.id, revokeRejectForm.value.reason)
    toast.success(res.message)
    revokeRejectForm.value = { id: '', reason: '' }
    await loadRevokeApps()
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    revokeRejecting.value = ''
  }
}
</script>

<template>
  <div class="cert-audit">
    <h2>证书审核</h2>

    <div class="toolbar">
      <label>
        状态
        <select v-model="filterStatus" @change="loadApps(1); loadRevokeApps()">
          <option value="pending">待审核</option>
          <option value="approved">已通过</option>
          <option value="rejected">已拒绝</option>
          <option value="">全部</option>
        </select>
      </label>
      <span class="count">证书申请 {{ total }} 条 / 撤销申请 {{ revokeTotal }} 条</span>
    </div>

    <section class="card">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="apps.length" class="responsive-table">
        <table>
          <thead>
            <tr><th>时间</th><th>姓名</th><th>机制</th><th>签发机构</th><th>算法</th><th>天数</th><th>状态</th><th>提交人</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="a in apps" :key="a.id">
              <td>{{ new Date(a.created_at).toLocaleString() }}</td>
              <td>{{ a.user_name }}</td>
              <td>双证书</td>
              <td><code>{{ a.issuer_cert_serial?.slice(0, 14) || '根 CA' }}{{ a.issuer_cert_serial ? '...' : '' }}</code></td>
              <td>{{ a.signature_algorithm }} / {{ a.encryption_algorithm }}</td>
              <td>{{ a.validity_days }} 天</td>
              <td><span :class="['badge', 'badge-' + a.status]">{{ statusLabel(a.status) }}</span></td>
              <td>{{ a.applied_by }}</td>
              <td class="actions">
                <button class="btn btn-sm btn-detail" @click="openDetail(a)">详情</button>
                <template v-if="a.status === 'pending'">
                  <button class="btn btn-sm btn-approve" :disabled="approving === a.id" @click="handleApprove(a.id)">
                    {{ approving === a.id ? '签发中...' : '通过' }}
                  </button>
                  <button class="btn btn-sm btn-reject" :disabled="approving === a.id" @click="openReject(a.id)">拒绝</button>
                </template>
                <span v-else-if="a.status === 'approved'" class="hint">
                  签名 {{ a.issued_cert_serial?.slice(0, 10) || '-' }}... / 加密 {{ a.issued_encrypt_cert_serial?.slice(0, 10) || '-' }}...
                </span>
                <span v-else class="hint">{{ a.reject_reason || '已拒绝' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-state">暂无申请记录</div>
    </section>

    <section class="card">
      <h3 class="card-title">撤销申请审核</h3>
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="revokeApps.length" class="responsive-table">
        <table>
          <thead>
            <tr><th>时间</th><th>证书序列号</th><th>原因</th><th>状态</th><th>提交人</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="a in revokeApps" :key="a.id">
              <td>{{ new Date(a.created_at).toLocaleString() }}</td>
              <td><code>{{ a.cert_serial_number.slice(0, 20) }}...</code></td>
              <td>{{ a.reason }}</td>
              <td><span :class="['badge', 'badge-' + a.status]">{{ statusLabel(a.status) }}</span></td>
              <td>{{ a.applied_by }}</td>
              <td class="actions">
                <template v-if="a.status === 'pending'">
                  <button class="btn btn-sm btn-approve" :disabled="revokeApproving === a.id" @click="handleApproveRevocation(a.id)">
                    {{ revokeApproving === a.id ? '撤销中...' : '通过' }}
                  </button>
                  <button class="btn btn-sm btn-reject" :disabled="revokeApproving === a.id" @click="openRevokeReject(a.id)">拒绝</button>
                </template>
                <span v-else class="hint">{{ a.reject_reason || a.reviewed_by || '-' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-state">暂无撤销申请</div>
    </section>

    <div v-if="rejectForm.id" class="modal-overlay" @click.self="rejectForm = { id: '', reason: '' }">
      <div class="modal">
        <h3>拒绝申请</h3>
        <label>
          拒绝原因
          <textarea v-model="rejectForm.reason" rows="3" maxlength="512" placeholder="请输入拒绝原因"></textarea>
        </label>
        <div class="modal-actions">
          <button class="btn btn-primary" :disabled="rejecting !== '' || !rejectForm.reason" @click="handleReject">
            {{ rejecting ? '提交中...' : '确认拒绝' }}
          </button>
          <button class="btn btn-ghost" @click="rejectForm = { id: '', reason: '' }">取消</button>
        </div>
      </div>
    </div>

    <div v-if="revokeRejectForm.id" class="modal-overlay" @click.self="revokeRejectForm = { id: '', reason: '' }">
      <div class="modal">
        <h3>拒绝撤销申请</h3>
        <label>
          拒绝原因
          <textarea v-model="revokeRejectForm.reason" rows="3" maxlength="512" placeholder="请输入拒绝原因"></textarea>
        </label>
        <div class="modal-actions">
          <button class="btn btn-primary" :disabled="revokeRejecting !== '' || !revokeRejectForm.reason" @click="handleRejectRevocation">
            {{ revokeRejecting ? '提交中...' : '确认拒绝' }}
          </button>
          <button class="btn btn-ghost" @click="revokeRejectForm = { id: '', reason: '' }">取消</button>
        </div>
      </div>
    </div>

    <div v-if="selectedApp" class="modal-overlay" @click.self="selectedApp = null">
      <div class="modal modal-detail">
        <h3>申请详情</h3>
        <div class="detail-grid">
          <div class="detail-item"><label>申请 ID</label><span>{{ selectedApp.id }}</span></div>
          <div class="detail-item"><label>姓名</label><span>{{ selectedApp.user_name }}</span></div>
          <div class="detail-item"><label>邮箱</label><span>{{ selectedApp.email || '-' }}</span></div>
          <div class="detail-item"><label>组织</label><span>{{ selectedApp.organization || '-' }}</span></div>
          <div class="detail-item"><label>部门</label><span>{{ selectedApp.department || '-' }}</span></div>
          <div class="detail-item"><label>证书类型</label><span>{{ selectedApp.cert_type }}</span></div>
          <div class="detail-item"><label>有效期</label><span>{{ selectedApp.validity_days }} 天</span></div>
          <div class="detail-item"><label>签名算法</label><span>{{ selectedApp.signature_algorithm }}</span></div>
          <div class="detail-item"><label>加密算法</label><span>{{ selectedApp.encryption_algorithm }}</span></div>
          <div class="detail-item"><label>签发机构</label><span><code>{{ selectedApp.issuer_cert_serial?.slice(0, 14) || '根 CA' }}{{ selectedApp.issuer_cert_serial ? '...' : '' }}</code></span></div>
          <div class="detail-item"><label>状态</label><span :class="['badge', 'badge-' + selectedApp.status]">{{ statusLabel(selectedApp.status) }}</span></div>
          <div class="detail-item"><label>提交人</label><span>{{ selectedApp.applied_by }}</span></div>
          <div class="detail-item"><label>审核人</label><span>{{ selectedApp.reviewed_by || '-' }}</span></div>
          <div class="detail-item"><label>已签发签名证书</label><span><code>{{ selectedApp.issued_cert_serial || '-' }}</code></span></div>
          <div class="detail-item"><label>已签发加密证书</label><span><code>{{ selectedApp.issued_encrypt_cert_serial || '-' }}</code></span></div>
          <div class="detail-item"><label>拒绝原因</label><span>{{ selectedApp.reject_reason || '-' }}</span></div>
          <div class="detail-item"><label>申请时间</label><span>{{ new Date(selectedApp.created_at).toLocaleString() }}</span></div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-primary" @click="selectedApp = null">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cert-audit h2 { margin-bottom: 1.5rem; font-size: 1.5rem; }
.toolbar { display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem; }
.toolbar label { display: flex; align-items: center; gap: 0.35rem; font-size: 0.85rem; color: #555; }
.toolbar select { padding: 0.4rem 0.6rem; border: 1px solid #ccc; border-radius: 6px; }
.count, .hint, .loading, .empty-state { color: #888; font-size: 0.85rem; }
.card { background: #fff; border-radius: 8px; padding: 1.5rem; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #eee; font-size: 0.85rem; }
th { color: #666; font-weight: 600; }
.badge { padding: 0.2rem 0.65rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }
.badge-pending { background: #fff3cd; color: #856404; }
.badge-approved { background: #d4edda; color: #155724; }
.badge-rejected { background: #f8d7da; color: #721c24; }
.actions { display: flex; gap: 0.4rem; }
.btn { padding: 0.45rem 0.9rem; border: none; border-radius: 6px; cursor: pointer; font-size: 0.82rem; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-sm { padding: 0.3rem 0.65rem; }
.btn-detail { background: #0f3460; color: #fff; }
.btn-approve { background: #28a745; color: #fff; }
.btn-reject { background: #dc3545; color: #fff; }
.btn-primary { background: #0f3460; color: #fff; }
.btn-ghost { background: transparent; color: #666; border: 1px solid #ccc; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 200; }
.modal { background: #fff; border-radius: 8px; padding: 1.5rem; width: 400px; max-width: 90vw; }
.modal h3 { margin-bottom: 1rem; }
.modal label { display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.85rem; color: #555; }
.modal textarea { padding: 0.5rem; border: 1px solid #ccc; border-radius: 6px; resize: vertical; }
.modal-detail { width: 560px; max-width: 90vw; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; max-height: 60vh; overflow-y: auto; }
.detail-item { display: flex; flex-direction: column; gap: 0.15rem; }
.detail-item label { font-size: 0.75rem; color: #888; font-weight: 600; }
.detail-item span { font-size: 0.85rem; color: #333; word-break: break-all; }
.detail-item code { font-size: 0.78rem; background: #f0f0f0; padding: 0.1rem 0.3rem; border-radius: 3px; }
.modal-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1rem; }
</style>
