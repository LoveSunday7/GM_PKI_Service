<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { certApi } from '@/api'
import { useToast } from '@/composables/useToast'
import { formatError } from '@/utils/errors'

defineOptions({ name: 'CertApplyPage' })

const toast = useToast()
const submitting = ref(false)
const myAppsLoading = ref(true)
const myApps = ref<Array<Record<string, unknown>>>([])

const form = ref({
  user_name: '',
  email: '',
  organization: '',
  department: '',
  province: '',
  city: '',
  cert_type: 'sign',
  validity_days: 365,
})

async function loadMyApps() {
  myAppsLoading.value = true
  try {
    const res = await certApi.applications({ page_size: 50 })
    myApps.value = res.items as unknown as Array<Record<string, unknown>>
  } catch {
    myApps.value = []
  } finally {
    myAppsLoading.value = false
  }
}

onMounted(loadMyApps)

async function handleApply() {
  submitting.value = true
  try {
    const payload = { ...form.value }
    const res = await certApi.apply(payload)
    toast.success(res.message)
    form.value.user_name = ''
    form.value.email = ''
    await loadMyApps()
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    submitting.value = false
  }
}

function statusLabel(s: string) {
  if (s === 'pending') return '待审核'
  if (s === 'approved') return '已通过'
  if (s === 'rejected') return '已拒绝'
  return s
}
</script>

<template>
  <div class="cert-apply">
    <h2>证书申请</h2>

    <section class="card">
      <h3 class="card-title">提交新申请</h3>
      <form class="form-grid" @submit.prevent="handleApply">
        <label>姓名 *<input v-model="form.user_name" required maxlength="128" placeholder="请输入申请人姓名" /></label>
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
        <label>有效期(天)<input v-model.number="form.validity_days" type="number" min="1" max="36500" /></label>
        <div class="form-actions">
          <button class="btn btn-primary" type="submit" :disabled="submitting || !form.user_name">
            {{ submitting ? '提交中...' : '提交申请' }}
          </button>
        </div>
      </form>
    </section>

    <section class="card">
      <h3 class="card-title">申请记录</h3>
      <div v-if="myAppsLoading" class="loading">加载中...</div>
      <div v-else-if="myApps.length" class="responsive-table">
        <table>
          <thead>
            <tr><th>时间</th><th>姓名</th><th>类型</th><th>状态</th><th>审核人</th><th>结果</th></tr>
          </thead>
          <tbody>
            <tr v-for="a in myApps" :key="a.id as string">
              <td>{{ new Date(a.created_at as string).toLocaleString() }}</td>
              <td>{{ a.user_name }}</td>
              <td>{{ a.cert_type === 'sign' ? '签名' : '加密' }}</td>
              <td><span :class="['badge', 'badge-' + a.status]">{{ statusLabel(a.status as string) }}</span></td>
              <td>{{ a.reviewed_by || '-' }}</td>
              <td>{{ a.reject_reason || (a.issued_cert_serial ? `序列号 ${(a.issued_cert_serial as string).slice(0, 14)}...` : '-') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-state">暂无申请记录</div>
    </section>
  </div>
</template>

<style scoped>
.cert-apply h2 { margin-bottom: 1.5rem; font-size: 1.5rem; }
.card { background: #fff; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.25rem; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.card-title { font-size: 1.05rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid #f0f0f0; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
label { display: flex; flex-direction: column; font-size: 0.85rem; color: #555; gap: 0.3rem; }
input, select { padding: 0.5rem 0.75rem; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 0.9rem; }
.form-actions { grid-column: 1 / -1; }
.btn { padding: 0.6rem 1.5rem; border: none; border-radius: 6px; cursor: pointer; font-size: 0.95rem; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: #0f3460; color: #fff; }
.loading, .empty-state { color: #888; }
.badge { padding: 0.2rem 0.65rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }
.badge-pending { background: #fff3cd; color: #856404; }
.badge-approved { background: #d4edda; color: #155724; }
.badge-rejected { background: #f8d7da; color: #721c24; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #eee; font-size: 0.85rem; }
th { color: #666; font-weight: 600; }
</style>
