<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { certApi } from '@/api'
import { useToast } from '@/composables/useToast'
import { formatError } from '@/utils/errors'

defineOptions({ name: 'CertAuditPage' })

const toast = useToast()
const loading = ref(true)
const apps = ref<Array<Record<string, unknown>>>([])
const total = ref(0)
const page = ref(1)
const filterStatus = ref('pending')
const approving = ref('')
const rejecting = ref('')
const rejectForm = ref({ id: '', reason: '' })

function statusLabel(s: string) {
  if (s === 'pending') return '⏳ 待审核'
  if (s === 'approved') return '✅ 已通过'
  if (s === 'rejected') return '❌ 已拒绝'
  return s
}

async function loadApps(p = 1) {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: p, page_size: 20 }
    if (filterStatus.value) params.status = filterStatus.value
    const res = await certApi.applications(params as { status?: string; page?: number; page_size?: number })
    apps.value = res.items as unknown as Array<Record<string, unknown>>
    total.value = res.total
    page.value = res.page
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    loading.value = false
  }
}

onMounted(() => loadApps())

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
</script>

<template>
  <div class="cert-audit">
    <h2>🔍 证书审核</h2>

    <!-- 筛选栏 -->
    <div class="toolbar">
      <label>
        状态
        <select v-model="filterStatus" @change="loadApps(1)">
          <option value="pending">待审核</option>
          <option value="approved">已通过</option>
          <option value="rejected">已拒绝</option>
          <option value="">全部</option>
        </select>
      </label>
      <span class="count">共 {{ total }} 条</span>
    </div>

    <!-- 申请列表 -->
    <section class="card">
      <div v-if="loading" class="skeleton-table">
        <div v-for="i in 3" :key="i" class="skeleton-row">
          <div class="skeleton skeleton-cell" style="width:16%" />
          <div class="skeleton skeleton-cell" style="width:10%" />
          <div class="skeleton skeleton-cell" style="width:8%" />
          <div class="skeleton skeleton-cell" style="width:10%" />
          <div class="skeleton skeleton-cell" style="width:20%" />
        </div>
      </div>

      <template v-else-if="apps.length">
        <div class="responsive-table">
        <table>
          <thead>
            <tr><th>时间</th><th>姓名</th><th>类型</th><th>天数</th><th>状态</th><th>提交人</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="a in apps" :key="a.id as string">
              <td data-label="时间">{{ new Date(a.created_at as string).toLocaleString() }}</td>
              <td data-label="姓名">{{ a.user_name }}</td>
              <td data-label="类型">{{ a.cert_type === 'sign' ? '签名' : '加密' }}</td>
              <td data-label="天数">{{ a.validity_days }}天</td>
              <td data-label="状态"><span :class="['badge', 'badge-' + a.status]">{{ statusLabel(a.status as string) }}</span></td>
              <td data-label="提交人">{{ a.applied_by }}</td>
              <td data-label="操作" class="actions">
                <template v-if="a.status === 'pending'">
                  <button class="btn btn-sm btn-approve" :disabled="approving === a.id" @click="handleApprove(a.id as string)">
                    {{ approving === a.id ? '⏳' : '✅ 通过' }}
                  </button>
                  <button class="btn btn-sm btn-reject" :disabled="approving === a.id" @click="openReject(a.id as string)">
                    ❌ 拒绝
                  </button>
                </template>
                <span v-else-if="a.status === 'approved'" class="hint">
                  签发: {{ (a.issued_cert_serial as string)?.slice(0, 12) }}...
                </span>
                <span v-else class="hint" :title="a.reject_reason as string">
                  {{ (a.reject_reason as string)?.slice(0, 20) || '已拒绝' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
        </div>

        <!-- 分页 -->
        <div class="pager" v-if="total > 20">
          <button :disabled="page <= 1" @click="loadApps(page - 1)">◀ 上一页</button>
          <span>{{ page }} / {{ Math.ceil(total / 20) }}</span>
          <button :disabled="page >= Math.ceil(total / 20)" @click="loadApps(page + 1)">下一页 ▶</button>
        </div>
      </template>
      <div v-else class="empty-state">
        <div class="empty-icon">🔍</div>
        <div class="empty-title">暂无申请记录</div>
      </div>
    </section>

    <!-- 拒绝原因弹窗 -->
    <div v-if="rejectForm.id" class="modal-overlay" @click.self="rejectForm = { id: '', reason: '' }">
      <div class="modal">
        <h3>❌ 拒绝申请</h3>
        <div class="modal-body">
          <label>
            拒绝原因
            <textarea v-model="rejectForm.reason" rows="3" placeholder="请填写拒绝原因..." maxlength="512"></textarea>
          </label>
        </div>
        <div class="modal-actions">
          <button class="btn btn-primary" :disabled="rejecting !== '' || !rejectForm.reason" @click="handleReject">
            {{ rejecting ? '⏳ 提交中...' : '确认拒绝' }}
          </button>
          <button class="btn btn-ghost" @click="rejectForm = { id: '', reason: '' }">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cert-audit h2 { margin-bottom: 1.5rem; font-size: 1.5rem; }
.toolbar { display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem; }
.toolbar label { display: flex; align-items: center; gap: 0.35rem; font-size: 0.85rem; color: #555; }
.toolbar select { padding: 0.4rem 0.6rem; border: 1px solid #ccc; border-radius: 6px; font-size: 0.85rem; }
.toolbar .count { font-size: 0.85rem; color: #888; }
.card { background: #fff; border-radius: 12px; padding: 1.5rem; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #eee; font-size: 0.85rem; }
th { color: #666; font-weight: 600; }
.badge { padding: 0.2rem 0.65rem; border-radius: 20px; font-size: 0.78rem; font-weight: 600; }
.badge-pending { background: #fff3cd; color: #856404; }
.badge-approved { background: #d4edda; color: #155724; }
.badge-rejected { background: #f8d7da; color: #721c24; }
.btn { padding: 0.4rem 0.9rem; border: none; border-radius: 6px; cursor: pointer; font-size: 0.82rem; transition: all 0.15s; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-sm { padding: 0.3rem 0.65rem; font-size: 0.78rem; }
.btn-approve { background: #28a745; color: #fff; }
.btn-approve:hover:not(:disabled) { background: #218838; }
.btn-reject { background: #dc3545; color: #fff; }
.btn-reject:hover:not(:disabled) { background: #c82333; }
.btn-primary { background: #0f3460; color: #fff; }
.btn-ghost { background: transparent; color: #666; border: 1px solid #ccc; }
.hint { font-size: 0.78rem; color: #888; }
.actions { display: flex; gap: 0.4rem; }
.pager { display: flex; align-items: center; justify-content: center; gap: 0.75rem; margin-top: 1rem; }
.pager button { padding: 0.4rem 0.85rem; border: 1px solid #999; background: #fff; border-radius: 6px; cursor: pointer; font-weight: 500; color: #333; }
.pager button:disabled { opacity: 0.25; cursor: not-allowed; }
.pager button:hover:not(:disabled) { background: #0f3460; color: #fff; border-color: #0f3460; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 200; }
.modal { background: #fff; border-radius: 12px; padding: 1.5rem; width: 400px; max-width: 90vw; }
.modal h3 { margin-bottom: 1rem; }
.modal-body { margin-bottom: 1rem; }
.modal-body label { display: flex; flex-direction: column; gap: 0.3rem; font-size: 0.85rem; color: #555; }
.modal-body textarea { padding: 0.5rem; border: 1px solid #ccc; border-radius: 6px; font-size: 0.9rem; resize: vertical; }
.modal-actions { display: flex; gap: 0.5rem; justify-content: flex-end; }
</style>
