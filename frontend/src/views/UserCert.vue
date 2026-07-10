<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { caApi, certApi, type CertChainResponse, type CertDetail, type CertIssueResponse, type CertListItem } from '@/api'
import { useToast } from '@/composables/useToast'
import { formatError } from '@/utils/errors'

defineOptions({ name: 'UserCertPage' })

const toast = useToast()
const caInitialized = ref(false)
const loading = ref(false)
const certLoading = ref(true)
const certs = ref<CertListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filterType = ref('')
const filterStatus = ref('')
const selectedCert = ref<CertDetail | null>(null)
const certStatus = ref<{ status?: string; revoked_at?: string; reason?: string } | null>(null)
const chainData = ref<CertChainResponse | null>(null)
const issueResult = ref<CertIssueResponse | null>(null)

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

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

async function loadCAStatus() {
  const status = await caApi.status()
  caInitialized.value = status.initialized
}

async function loadCerts(p = 1) {
  certLoading.value = true
  try {
    const params: { page: number; page_size: number; cert_type?: string; status?: string } = {
      page: p,
      page_size: pageSize.value,
    }
    if (filterType.value) params.cert_type = filterType.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await certApi.list(params)
    certs.value = res.items
    total.value = res.total
    page.value = res.page
    pageSize.value = res.page_size
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    certLoading.value = false
  }
}

onMounted(async () => {
  await loadCAStatus()
  await loadCerts()
})

async function handleIssue() {
  loading.value = true
  issueResult.value = null
  try {
    const payload: Record<string, unknown> = { ...form.value }
    if (!payload.public_key_pem) delete payload.public_key_pem
    const res = await certApi.issue(payload)
    issueResult.value = res
    toast.success(String(res.message || '证书签发成功'))
    await loadCerts(1)
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    loading.value = false
  }
}

async function showDetail(serial: string) {
  selectedCert.value = null
  certStatus.value = null
  chainData.value = null
  try {
    const [detail, status, chain] = await Promise.all([
      certApi.detail(serial),
      certApi.status(serial),
      certApi.chain(serial).catch(() => null),
    ])
    selectedCert.value = detail
    certStatus.value = status
    chainData.value = chain
  } catch (e: unknown) {
    toast.error(formatError(e))
  }
}

async function handleDownload(serial: string) {
  try {
    await certApi.download(serial)
  } catch (e: unknown) {
    toast.error(formatError(e))
  }
}

async function copyText(text: string) {
  await navigator.clipboard.writeText(text)
  toast.success('已复制')
}

function closeDetail() {
  selectedCert.value = null
  certStatus.value = null
  chainData.value = null
}
</script>

<template>
  <div class="user-cert">
    <h2>用户证书管理</h2>

    <section v-if="caInitialized" class="section">
      <h3>签发新证书</h3>
      <form class="form-grid" @submit.prevent="handleIssue">
        <label>用户姓名 *<input v-model="form.user_name" required maxlength="128" placeholder="例如: 张三" /></label>
        <label>邮箱<input v-model="form.email" type="email" maxlength="255" /></label>
        <label>组织<input v-model="form.organization" maxlength="255" /></label>
        <label>部门<input v-model="form.department" maxlength="255" /></label>
        <label>省份<input v-model="form.province" maxlength="128" /></label>
        <label>城市<input v-model="form.city" maxlength="128" /></label>
        <label>证书类型
          <select v-model="form.cert_type">
            <option value="sign">签名证书</option>
            <option value="encrypt">加密证书</option>
            <option value="both">双证书(签名+加密)</option>
          </select>
        </label>
        <label>有效期(天)<input v-model.number="form.validity_days" type="number" min="1" max="36500" /></label>
        <label class="full-width">公钥 PEM(可选)
          <textarea v-model="form.public_key_pem" rows="3" placeholder="不填写则自动生成密钥对"></textarea>
        </label>
        <div class="form-actions">
          <button type="submit" :disabled="loading || !form.user_name">{{ loading ? '签发中...' : '签发证书' }}</button>
        </div>
      </form>
    </section>

    <section v-else class="section">
      <p class="warn">请先初始化 CA。</p>
    </section>

    <section v-if="issueResult" class="section issue-result">
      <div class="detail-header">
        <h3>{{ issueResult.message }}</h3>
        <button class="btn-close" @click="issueResult = null">关闭</button>
      </div>
      <div class="result-grid">
        <div v-if="issueResult.sign_serial_number"><span>签名证书</span><code>{{ issueResult.sign_serial_number }}</code></div>
        <div v-if="issueResult.encrypt_serial_number"><span>加密证书</span><code>{{ issueResult.encrypt_serial_number }}</code></div>
        <div><span>用户 DN</span><strong>{{ issueResult.subject_dn }}</strong></div>
        <div><span>根 DN</span><strong>{{ issueResult.root_dn }}</strong></div>
      </div>
      <p class="hint">证书 PEM、根证书和私钥已在响应中返回，可从证书详情或下载按钮查看证书链。</p>
    </section>

    <section class="section">
      <h3>已签发证书</h3>
      <div class="filter-bar">
        <label>类型
          <select v-model="filterType" @change="loadCerts(1)">
            <option value="">全部</option>
            <option value="sign">签名证书</option>
            <option value="encrypt">加密证书</option>
          </select>
        </label>
        <label>状态
          <select v-model="filterStatus" @change="loadCerts(1)">
            <option value="">全部</option>
            <option value="active">有效</option>
            <option value="revoked">已撤销</option>
          </select>
        </label>
        <span class="filter-count">共 {{ total }} 张</span>
      </div>

      <div v-if="certLoading" class="loading">加载中...</div>
      <div v-else-if="certs.length" class="responsive-table">
        <table>
          <thead>
            <tr><th>序列号</th><th>类型</th><th>主题 DN</th><th>用户</th><th>到期日期</th><th>状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="c in certs" :key="c.id">
              <td class="clickable" @click="showDetail(c.serial_number)"><code>{{ c.serial_number.slice(0, 14) }}...</code></td>
              <td><span :class="['badge', c.cert_type === 'sign' ? 'badge-blue' : 'badge-purple']">{{ c.cert_type === 'sign' ? '签名' : '加密' }}</span></td>
              <td class="clickable" @click="showDetail(c.serial_number)">{{ c.subject_dn }}</td>
              <td>{{ c.user_name }}</td>
              <td>{{ new Date(c.not_after).toLocaleDateString() }}</td>
              <td><span :class="['badge', c.status === 'active' ? 'badge-green' : 'badge-red']">{{ c.status === 'active' ? '有效' : '已撤销' }}</span></td>
              <td><button class="btn-sm" @click="handleDownload(c.serial_number)">下载链</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-state">暂无已签发证书</div>

      <div v-if="totalPages > 1" class="pager">
        <button :disabled="page <= 1" @click="loadCerts(page - 1)">上一页</button>
        <span>{{ page }} / {{ totalPages }}</span>
        <button :disabled="page >= totalPages" @click="loadCerts(page + 1)">下一页</button>
      </div>
    </section>

    <section v-if="selectedCert" class="section">
      <div class="detail-header">
        <h3>证书详情</h3>
        <button class="btn-close" @click="closeDetail">关闭</button>
      </div>
      <div v-if="certStatus" class="status-bar">
        <span :class="['badge', certStatus.status === 'active' ? 'badge-green' : 'badge-red']">
          {{ certStatus.status === 'active' ? '有效' : '已撤销' }}
        </span>
      </div>
      <dl class="detail-grid">
        <dt>序列号</dt><dd><code>{{ selectedCert.serial_number }}</code></dd>
        <dt>证书类型</dt><dd>{{ selectedCert.cert_type === 'sign' ? '签名证书' : '加密证书' }}</dd>
        <dt>主题 DN</dt><dd>{{ selectedCert.subject_dn }}</dd>
        <dt>签发者 DN</dt><dd>{{ selectedCert.issuer_dn }}</dd>
        <dt>用户</dt><dd>{{ selectedCert.user_name }}</dd>
        <dt>邮箱</dt><dd>{{ selectedCert.email || '-' }}</dd>
        <dt>签名算法</dt><dd>{{ selectedCert.signature_algorithm }}</dd>
        <dt>有效期</dt><dd>{{ selectedCert.not_before }} 至 {{ selectedCert.not_after }}</dd>
        <dt>证书 PEM</dt>
        <dd>
          <pre class="pem-preview">{{ selectedCert.cert_pem.slice(0, 500) }}...</pre>
          <button class="btn-copy" @click="copyText(selectedCert.cert_pem)">复制 PEM</button>
        </dd>
      </dl>

      <div v-if="chainData?.chain.length" class="chain-view">
        <h4>证书链 <span :class="chainData.verified ? 'chain-ok' : 'chain-warn'">{{ chainData.verified ? '验证通过' : '验证未通过' }}</span></h4>
        <div class="chain-cards">
          <div v-for="(node, idx) in chainData.chain" :key="idx" class="chain-step">
            <div :class="['chain-card', node.cert_type === 'root' ? 'chain-root' : 'chain-user']">
              <div class="chain-type">{{ node.cert_type === 'root' ? '根 CA' : node.cert_type === 'sign' ? '签名证书' : '加密证书' }}</div>
              <div class="chain-dn">{{ node.subject_dn }}</div>
              <div class="chain-meta">
                <code>{{ node.serial_number.slice(0, 18) }}...</code>
                <span :class="['badge', node.status === 'active' ? 'badge-green' : 'badge-red']">{{ node.status === 'active' ? '有效' : '已撤销' }}</span>
              </div>
            </div>
            <div v-if="idx < chainData.chain.length - 1" class="chain-arrow">↓ 签发</div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.user-cert h2 { margin-bottom: 1.5rem; }
.section { background: #fff; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.25rem; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.section h3 { margin-bottom: 1rem; font-size: 1.1rem; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
.full-width { grid-column: 1 / -1; }
label { display: flex; flex-direction: column; font-size: 0.85rem; color: #555; gap: 0.3rem; }
input, select, textarea { padding: 0.5rem 0.75rem; border: 1px solid #d0d0d0; border-radius: 6px; font-size: 0.9rem; }
textarea { resize: vertical; font-family: monospace; }
.form-actions { grid-column: 1 / -1; }
button { padding: 0.55rem 1.2rem; background: #1a1a2e; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-sm { padding: 0.3rem 0.7rem; font-size: 0.8rem; background: #555; }
.btn-close { background: transparent; color: #666; border: 1px solid #ccc; padding: 0.35rem 0.75rem; }
.filter-bar { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.75rem; flex-wrap: wrap; }
.filter-bar label { flex-direction: row; align-items: center; margin: 0; }
.filter-count, .hint, .loading, .empty-state { color: #888; font-size: 0.85rem; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #eee; font-size: 0.85rem; }
th { color: #666; font-weight: 600; }
.clickable { cursor: pointer; }
code { font-size: 0.8rem; background: #f0f0f0; padding: 0.15rem 0.35rem; border-radius: 4px; }
.badge { padding: 0.18rem 0.6rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }
.badge-green { background: #d4edda; color: #155724; }
.badge-red { background: #f8d7da; color: #721c24; }
.badge-blue { background: #d1ecf1; color: #0c5460; }
.badge-purple { background: #e2d9f3; color: #5a3d7a; }
.warn { color: #856404; }
.issue-result { border: 1px solid #b7dfc1; background: #f8fff8; }
.result-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0.75rem; }
.result-grid div { display: flex; flex-direction: column; gap: 0.25rem; }
.result-grid span { color: #777; font-size: 0.78rem; }
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.detail-header h3 { margin-bottom: 0; }
.status-bar { margin-bottom: 1rem; }
.detail-grid { display: grid; grid-template-columns: 140px 1fr; gap: 0.35rem 1rem; font-size: 0.85rem; }
.detail-grid dt { color: #666; font-weight: 600; }
.detail-grid dd { word-break: break-all; }
.pem-preview { background: #f8f8f8; padding: 0.5rem; border-radius: 6px; font-size: 0.72rem; font-family: monospace; white-space: pre-wrap; word-break: break-all; max-height: 120px; overflow-y: auto; margin-bottom: 0.4rem; }
.btn-copy { padding: 0.3rem 0.7rem; font-size: 0.78rem; background: transparent; color: #0f3460; border: 1px solid #0f3460; }
.chain-view { margin-top: 1.25rem; padding-top: 1rem; border-top: 1px solid #f0f0f0; }
.chain-ok { color: #28a745; font-weight: 600; }
.chain-warn { color: #dc3545; font-weight: 600; }
.chain-cards { display: flex; flex-direction: column; align-items: center; gap: 0.2rem; }
.chain-step { width: 100%; max-width: 520px; display: flex; flex-direction: column; align-items: center; }
.chain-card { width: 100%; background: #f8f9fa; border-radius: 8px; padding: 0.8rem 1rem; border-left: 4px solid #28a745; }
.chain-root { border-left-color: #0f3460; }
.chain-type { font-weight: 700; margin-bottom: 0.25rem; }
.chain-dn { font-size: 0.8rem; color: #555; word-break: break-all; }
.chain-meta { margin-top: 0.4rem; display: flex; gap: 0.5rem; align-items: center; }
.chain-arrow { margin: 0.35rem 0; color: #777; font-size: 0.82rem; }
.pager { display: flex; justify-content: center; align-items: center; gap: 0.75rem; margin-top: 1rem; }
</style>
