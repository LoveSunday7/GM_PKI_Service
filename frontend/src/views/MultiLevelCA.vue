<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { caApi, certApi, type CertIssueResponse, type CertListItem } from '@/api'
import { useToast } from '@/composables/useToast'
import { formatError } from '@/utils/errors'

defineOptions({ name: 'MultiLevelCAPage' })

const toast = useToast()
const caInitialized = ref(false)
const loading = ref(false)
const listLoading = ref(true)
const intermediateCAs = ref<CertListItem[]>([])
const issueResult = ref<CertIssueResponse | null>(null)
const serialQuery = ref('')

const form = ref({
  user_name: '',
  organization: '',
  department: '',
  province: '',
  city: '',
  validity_days: 1825,
  signature_algorithm: 'SM3WITHSM2',
  issuer_cert_serial: '',
})

const matchedCA = computed(() => {
  const q = serialQuery.value.trim().toLowerCase()
  if (!q) return null
  return intermediateCAs.value.find((c) => c.serial_number.toLowerCase().includes(q)) || null
})

async function loadCAStatus() {
  const status = await caApi.status()
  caInitialized.value = status.initialized
}

async function loadIntermediateCAs() {
  listLoading.value = true
  try {
    const res = await certApi.list({ cert_type: 'intermediate_ca', page_size: 100 })
    intermediateCAs.value = res.items
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    listLoading.value = false
  }
}

onMounted(async () => {
  await loadCAStatus()
  await loadIntermediateCAs()
})

async function handleIssueIntermediateCA() {
  loading.value = true
  issueResult.value = null
  try {
    const payload: Record<string, unknown> = {
      ...form.value,
      cert_type: 'intermediate_ca',
      encryption_algorithm: 'SM2',
    }
    if (!payload.issuer_cert_serial) delete payload.issuer_cert_serial
    const res = await certApi.issue(payload)
    issueResult.value = res
    toast.success(res.message)
    form.value.user_name = ''
    form.value.issuer_cert_serial = ''
    await loadIntermediateCAs()
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="multi-ca">
    <h2>多级证书</h2>

    <section v-if="!caInitialized" class="section">
      <p class="warn">请先初始化根 CA。</p>
    </section>

    <section v-else class="section">
      <h3>签发中间 CA</h3>
      <form class="form-grid" @submit.prevent="handleIssueIntermediateCA">
        <label>中间 CA 名称 *<input v-model="form.user_name" required maxlength="128" placeholder="例如: Department-CA" /></label>
        <label>组织<input v-model="form.organization" maxlength="255" /></label>
        <label>部门<input v-model="form.department" maxlength="255" /></label>
        <label>省份<input v-model="form.province" maxlength="128" /></label>
        <label>城市<input v-model="form.city" maxlength="128" /></label>
        <label>有效期(天)<input v-model.number="form.validity_days" type="number" min="1" max="36500" /></label>
        <label>签名算法
          <select v-model="form.signature_algorithm">
            <option value="SM3WITHSM2">SM3WITHSM2</option>
            <option value="SHA256WITHECDSA">SHA256WITHECDSA</option>
            <option value="SHA384WITHECDSA">SHA384WITHECDSA</option>
            <option value="SHA512WITHECDSA">SHA512WITHECDSA</option>
          </select>
        </label>
        <label class="full-width">上级中间 CA 序列号(可选)
          <input v-model="form.issuer_cert_serial" maxlength="64" placeholder="留空表示由根 CA 签发；填写则继续向下分级" />
        </label>
        <div class="form-actions">
          <button type="submit" :disabled="loading || !form.user_name">{{ loading ? '签发中...' : '签发中间 CA' }}</button>
        </div>
      </form>
    </section>

    <section v-if="issueResult" class="section result">
      <h3>{{ issueResult.message }}</h3>
      <div class="result-grid">
        <div><span>中间 CA 序列号</span><code>{{ issueResult.serial_number }}</code></div>
        <div><span>上级证书序列号</span><code>{{ issueResult.issuer_cert_serial || '根 CA' }}</code></div>
        <div><span>主题 DN</span><strong>{{ issueResult.subject_dn }}</strong></div>
      </div>
    </section>

    <section class="section">
      <h3>中间 CA 列表</h3>
      <div class="serial-search">
        <input v-model="serialQuery" placeholder="输入中间 CA 序列号过滤" />
      </div>
      <div v-if="listLoading" class="empty-state">加载中...</div>
      <div v-else-if="matchedCA || intermediateCAs.length" class="responsive-table">
        <table>
          <thead>
            <tr><th>序列号</th><th>主题 DN</th><th>到期日期</th><th>状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="c in (matchedCA ? [matchedCA] : intermediateCAs)" :key="c.id">
              <td><code>{{ c.serial_number }}</code></td>
              <td>{{ c.subject_dn }}</td>
              <td>{{ new Date(c.not_after).toLocaleDateString() }}</td>
              <td><span :class="['badge', c.status === 'active' ? 'badge-green' : 'badge-red']">{{ c.status === 'active' ? '有效' : '已撤销' }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-state">暂无中间 CA</div>
    </section>
  </div>
</template>

<style scoped>
.multi-ca h2 { margin-bottom: 1.5rem; }
.section { background: #fff; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.25rem; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.section h3 { margin-bottom: 1rem; font-size: 1.1rem; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }
.full-width { grid-column: 1 / -1; }
label { display: flex; flex-direction: column; font-size: 0.85rem; color: #555; gap: 0.3rem; }
input, select { padding: 0.5rem 0.75rem; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 0.9rem; }
.form-actions { grid-column: 1 / -1; }
button { padding: 0.55rem 1.2rem; background: #1a1a2e; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.warn { color: #856404; }
.result { border: 1px solid #b7dfc1; background: #f8fff8; }
.result-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 0.75rem; }
.result-grid div { display: flex; flex-direction: column; gap: 0.25rem; }
.result-grid span, .empty-state { color: #888; font-size: 0.85rem; }
.serial-search { margin-bottom: 0.75rem; }
.serial-search input { width: 100%; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #eee; font-size: 0.85rem; }
th { color: #666; font-weight: 600; }
code { font-size: 0.78rem; background: #f0f0f0; padding: 0.15rem 0.35rem; border-radius: 4px; word-break: break-all; }
.badge { padding: 0.18rem 0.6rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }
.badge-green { background: #d4edda; color: #155724; }
.badge-red { background: #f8d7da; color: #721c24; }
</style>
