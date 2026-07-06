<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useCRLStore } from '@/stores/crl'
import { useCAStore } from '@/stores/ca'
import { useCertStore } from '@/stores/cert'
import { crlApi } from '@/api'
import { useToast } from '@/composables/useToast'
import { formatError } from '@/utils/errors'

const toast = useToast()
const crlStore = useCRLStore()
const caStore = useCAStore()
const certStore = useCertStore()

const loading = ref(false)
const crlCopied = ref(false)

// ── CRL 历史 ───────────────────────────────────────────────────
const history = ref<Array<Record<string, unknown>>>([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyLoading = ref(false)
const PAGE_SIZE = 10

async function loadHistory(page = 1) {
  historyLoading.value = true
  try {
    const res = await crlApi.history(page, PAGE_SIZE)
    history.value = res.items as unknown as Array<Record<string, unknown>>
    historyTotal.value = res.total
    historyPage.value = res.page
  } catch { /* ignore */ }
  finally { historyLoading.value = false }
}

// ── 序列号自动补全 ─────────────────────────────────────────────
const showSuggestions = ref(false)

const serialSuggestions = computed(() => {
  const q = revokeForm.value.cert_serial_number.trim().toLowerCase()
  if (!q) return []
  return certStore.certs
    .filter((c: { serial_number: string; status: string }) =>
      c.serial_number.toLowerCase().includes(q) && c.status === 'active'
    )
    .slice(0, 8)
})

function selectSuggestion(serial: string) {
  revokeForm.value.cert_serial_number = serial
  showSuggestions.value = false
}

function onSerialFocus() {
  showSuggestions.value = true
}

function onSerialBlur() {
  // 延迟隐藏以允许点击建议项
  setTimeout(() => { showSuggestions.value = false }, 150)
}

const reasonLabels: Record<string, string> = {
  unspecified: '未指定',
  keyCompromise: '密钥泄露',
  affiliationChanged: '隶属关系变更',
  superseded: '已被取代',
  cessationOfOperation: '停止运营',
}

const revokeForm = ref({
  cert_serial_number: '',
  reason: 'unspecified',
})

onMounted(async () => {
  await caStore.fetchStatus()
  await Promise.all([crlStore.fetchCurrent(), certStore.fetchList(), loadHistory()])
})

async function handleRevoke() {
  loading.value = true
  try {
    const res = await crlStore.revoke(revokeForm.value)
    const revokeRes = res as { cert_serial_number?: string }
    toast.success(`撤销成功: ${revokeRes.cert_serial_number?.slice(0, 20)}...`)
    revokeForm.value.cert_serial_number = ''
    await certStore.fetchList()
    await crlStore.fetchCurrent()
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    loading.value = false
  }
}

async function handleGenerate() {
  loading.value = true
  try {
    const genRes = await crlStore.generate() as { crl_number?: number; revoked_count?: number }
    toast.success(`CRL #${genRes.crl_number} 已生成，包含 ${genRes.revoked_count} 条撤销`)
    await crlStore.fetchCurrent()
    await loadHistory(1)
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    loading.value = false
  }
}

async function handleDownload() {
  try {
    await crlApi.download()
  } catch (e: unknown) {
    toast.error(formatError(e))
  }
}

async function copyCRLPEM(pem: string) {
  try {
    await navigator.clipboard.writeText(pem)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = pem
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  crlCopied.value = true
  setTimeout(() => { crlCopied.value = false }, 2000)
}
</script>

<template>
  <div class="crl">
    <h2>证书撤销列表 (CRL)</h2>

    <!-- 撤销表单 -->
    <section class="section" v-if="caStore.initialized">
      <h3>撤销证书</h3>
      <form @submit.prevent="handleRevoke" class="form-row">
        <label class="autocomplete-wrapper">
          证书序列号
          <input
            v-model="revokeForm.cert_serial_number"
            required
            placeholder="输入证书序列号搜索..."
            autocomplete="off"
            @focus="onSerialFocus"
            @blur="onSerialBlur"
            @input="showSuggestions = true"
          />
          <ul v-if="showSuggestions && serialSuggestions.length" class="suggestions">
            <li
              v-for="c in serialSuggestions"
              :key="c.serial_number"
              @mousedown.prevent="selectSuggestion(c.serial_number)"
            >
              <code>{{ (c as { serial_number: string }).serial_number?.slice(0, 20) }}...</code>
              <span class="sug-user">{{ (c as { user_name: string }).user_name }}</span>
              <span class="sug-type">{{ (c as { cert_type: string }).cert_type }}</span>
            </li>
          </ul>
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
        <div class="crl-actions">
          <button class="btn-sm" @click="handleDownload">⬇ 下载 CRL</button>
        </div>

        <!-- CRL PEM 预览 -->
        <div class="crl-pem" v-if="crlStore.currentCRL.crl_pem">
          <details>
            <summary>证书吊销列表 PEM</summary>
            <pre class="pem-preview">{{ (crlStore.currentCRL.crl_pem as string)?.slice(0, 500) }}{{ (crlStore.currentCRL.crl_pem as string)?.length > 500 ? '...' : '' }}</pre>
            <button class="btn-copy" @click="copyCRLPEM(crlStore.currentCRL.crl_pem as string)">
              {{ crlCopied ? '✅ 已复制' : '📋 复制 PEM' }}
            </button>
          </details>
        </div>

        <!-- 撤销列表 -->
        <div class="responsive-table">
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
              <td data-label="序列号"><code>{{ r.cert_serial_number?.slice(0, 20) }}...</code></td>
              <td data-label="撤销原因">{{ reasonLabels[r.reason] || r.reason }}</td>
              <td data-label="撤销时间">{{ new Date(r.revoked_at).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
        </div>
      </div>
      <div v-else class="empty-state">
        <div class="empty-icon">📋</div>
        <div class="empty-title">暂无 CRL 发布记录</div>
        <div class="empty-hint">撤销证书后点击"生成 CRL"即可创建第一条发布记录</div>
      </div>
    </section>

    <!-- CRL 历史记录 -->
    <section class="section">
      <h3>📋 CRL 历史记录</h3>
      <div v-if="historyLoading" class="loading">加载中...</div>
      <template v-else-if="history.length">
        <div class="responsive-table">
        <table>
          <thead>
            <tr>
              <th>CRL #</th>
              <th>签发者</th>
              <th>更新时间</th>
              <th>下次更新</th>
              <th>撤销数</th>
              <th>发布时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="h in history" :key="h.id as string">
              <td data-label="CRL #"><strong>#{{ h.crl_number }}</strong></td>
              <td data-label="签发者">{{ (h.issuer_dn as string)?.slice(0, 40) }}...</td>
              <td data-label="更新时间">{{ new Date(h.this_update as string).toLocaleString() }}</td>
              <td data-label="下次更新">{{ new Date(h.next_update as string).toLocaleString() }}</td>
              <td data-label="撤销数">{{ h.revoked_count }}</td>
              <td data-label="发布时间">{{ new Date(h.created_at as string).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
        </div>
        <div class="pager" v-if="historyTotal > PAGE_SIZE">
          <button :disabled="historyPage <= 1" @click="loadHistory(historyPage - 1)">◀ 上一页</button>
          <span>{{ historyPage }} / {{ Math.ceil(historyTotal / PAGE_SIZE) }}</span>
          <button :disabled="historyPage >= Math.ceil(historyTotal / PAGE_SIZE)" @click="loadHistory(historyPage + 1)">下一页 ▶</button>
        </div>
      </template>
      <div v-else class="empty-state">
        <div class="empty-icon">📋</div>
        <div class="empty-title">暂无 CRL 历史记录</div>
        <div class="empty-hint">生成 CRL 后历史记录将在此展示</div>
      </div>
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
.empty { color: #888; font-style: italic; }
.crl-actions { margin-top: 0.75rem; }
.btn-sm { padding: 0.35rem 0.8rem; font-size: 0.82rem; background: #555; }

/* CRL PEM */
.crl-pem { margin-top: 0.75rem; }
.crl-pem details { font-size: 0.85rem; }
.crl-pem summary { cursor: pointer; color: #0f3460; font-weight: 500; margin-bottom: 0.4rem; }
.pem-preview {
  background: #f8f8f8;
  padding: 0.5rem;
  border-radius: 6px;
  font-size: 0.72rem;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 150px;
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

.loading { color: #888; font-style: italic; }

/* 分页 */
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  margin-top: 1rem;
  font-size: 0.85rem;
}
.pager button {
  padding: 0.4rem 0.85rem;
  border: 1px solid #999;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.84rem;
  font-weight: 500;
  color: #333;
  transition: all 0.15s;
}
.pager button:disabled { opacity: 0.25; cursor: not-allowed; }
.pager button:hover:not(:disabled) { background: #0f3460; color: #fff; border-color: #0f3460; }
.pager .page-btn.active { background: #0f3460; color: #fff; border-color: #0f3460; }

/* 自动补全 */
.autocomplete-wrapper { position: relative; }
.suggestions {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: #fff;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  z-index: 100;
  list-style: none;
  margin: 2px 0 0;
  padding: 0.25rem 0;
  max-height: 260px;
  overflow-y: auto;
}
.suggestions li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  cursor: pointer;
  font-size: 0.8rem;
  transition: background 0.1s;
}
.suggestions li:hover { background: #f0f4f8; }
.suggestions li code { font-size: 0.72rem; }
.sug-user { color: #555; flex-shrink: 0; }
.sug-type { color: #999; font-size: 0.7rem; margin-left: auto; }
</style>
