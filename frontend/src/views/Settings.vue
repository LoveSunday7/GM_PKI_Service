<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { systemApi, type DatabaseInfo, type KeystoreInfo, type SystemConfig } from '@/api'

defineOptions({ name: 'SettingsPage' })

const loading = ref(true)
const config = ref<SystemConfig | null>(null)
const keystoreInfo = ref<KeystoreInfo | null>(null)
const dbInfo = ref<DatabaseInfo | null>(null)
const error = ref('')

const editingCaInfo = ref(false)
const caInfoSaving = ref(false)
const caInfoMsg = ref('')
const caInfoForm = ref({ ca_name: '', organization: '', default_signature_algorithm: '' })

const editingParams = ref(false)
const paramSaving = ref(false)
const paramMsg = ref('')
const editForm = ref({ ca_default_validity_days: 0, cert_default_validity_days: 0, crl_validity_hours: 0 })

async function loadData() {
  loading.value = true
  try {
    const [cfg, keystore, database] = await Promise.all([
      systemApi.getConfig(),
      systemApi.getKeystoreInfo(),
      systemApi.getDatabase(),
    ])
    config.value = cfg
    keystoreInfo.value = keystore
    dbInfo.value = database
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载系统配置失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

function startEditCaInfo() {
  if (!config.value) return
  caInfoForm.value = {
    ca_name: config.value.ca_name,
    organization: config.value.organization,
    default_signature_algorithm: config.value.default_signature_algorithm,
  }
  editingCaInfo.value = true
}

async function saveCaInfo() {
  caInfoSaving.value = true
  caInfoMsg.value = ''
  try {
    const res = await systemApi.updateConfig(caInfoForm.value)
    if (config.value) {
      config.value.ca_name = res.ca_name
      config.value.organization = res.organization
      config.value.default_signature_algorithm = res.default_signature_algorithm
    }
    caInfoMsg.value = res.message
    editingCaInfo.value = false
  } catch (e: unknown) {
    caInfoMsg.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    caInfoSaving.value = false
  }
}

function startEditParams() {
  if (!config.value) return
  editForm.value = {
    ca_default_validity_days: config.value.ca_default_validity_days,
    cert_default_validity_days: config.value.cert_default_validity_days,
    crl_validity_hours: config.value.crl_validity_hours,
  }
  editingParams.value = true
}

async function saveParams() {
  paramSaving.value = true
  paramMsg.value = ''
  try {
    const res = await systemApi.updateConfig(editForm.value)
    if (config.value) {
      config.value.ca_default_validity_days = res.ca_default_validity_days
      config.value.cert_default_validity_days = res.cert_default_validity_days
      config.value.crl_validity_hours = res.crl_validity_hours
    }
    paramMsg.value = res.message
    editingParams.value = false
  } catch (e: unknown) {
    paramMsg.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    paramSaving.value = false
  }
}
</script>

<template>
  <div class="settings">
    <h2>系统设置</h2>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else-if="config">
      <section class="card">
        <h3 class="card-title">应用信息</h3>
        <div class="info-grid">
          <div class="info-item"><span class="info-label">应用名称</span><span class="info-value">{{ config.app_name }}</span></div>
          <div class="info-item"><span class="info-label">版本</span><span class="info-value">v1.0.0</span></div>
          <div class="info-item"><span class="info-label">调试模式</span><span :class="['badge', config.debug ? 'badge-on' : 'badge-off']">{{ config.debug ? '开启' : '关闭' }}</span></div>
          <div class="info-item"><span class="info-label">数据库后端</span><span class="info-value">{{ config.database_type.toUpperCase() }}</span></div>
        </div>
      </section>

      <section class="card ca-card">
        <div class="ca-summary">
          <h3 class="card-title">CA 信息</h3>
          <div class="info-grid">
            <div class="info-item"><span class="info-label">CA 名称</span><span class="info-value">{{ config.ca_name }}</span></div>
            <div class="info-item"><span class="info-label">组织信息</span><span class="info-value">{{ config.organization }}</span></div>
            <div class="info-item"><span class="info-label">签名算法</span><span class="info-value"><code>{{ config.default_signature_algorithm }}</code></span></div>
          </div>
          <button v-if="!editingCaInfo" class="btn btn-primary" @click="startEditCaInfo">编辑</button>
          <p v-if="caInfoMsg" class="msg">{{ caInfoMsg }}</p>
        </div>
        <aside class="ca-editor">
          <template v-if="editingCaInfo">
            <h4>编辑 CA 信息</h4>
            <label>CA 名称<input v-model="caInfoForm.ca_name" maxlength="255" /></label>
            <label>组织信息<input v-model="caInfoForm.organization" maxlength="255" /></label>
            <label>签名算法
              <select v-model="caInfoForm.default_signature_algorithm">
                <option>SM3WITHSM2</option>
                <option>SHA256WITHRSA</option>
              </select>
            </label>
            <div class="actions">
              <button class="btn btn-primary" :disabled="caInfoSaving" @click="saveCaInfo">{{ caInfoSaving ? '保存中...' : '保存' }}</button>
              <button class="btn btn-ghost" :disabled="caInfoSaving" @click="editingCaInfo = false">取消</button>
            </div>
          </template>
        </aside>
      </section>

      <section class="card">
        <h3 class="card-title">数据库信息</h3>
        <div class="info-grid">
          <div class="info-item"><span class="info-label">数据库类型</span><span class="info-value">{{ dbInfo?.database_type?.toUpperCase() ?? '-' }}</span></div>
          <div class="info-item"><span class="info-label">连接状态</span><span :class="['badge', dbInfo?.connected ? 'badge-on' : 'badge-error']">{{ dbInfo?.connected ? '已连接' : '已断开' }}</span></div>
          <div class="info-item"><span class="info-label">数据表数量</span><span class="info-value">{{ dbInfo?.tables.length ?? '-' }}</span></div>
          <div class="info-item"><span class="info-label">总行数</span><span class="info-value">{{ dbInfo?.total_rows ?? '-' }}</span></div>
        </div>
        <div v-if="dbInfo?.tables.length" class="responsive-table table-list">
          <table>
            <thead><tr><th>表名</th><th>行数</th></tr></thead>
            <tbody>
              <tr v-for="t in dbInfo.tables" :key="t.name">
                <td><code>{{ t.name }}</code></td>
                <td>{{ t.row_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="card">
        <h3 class="card-title">密钥库信息</h3>
        <div class="info-grid">
          <div class="info-item info-wide"><span class="info-label">存储路径</span><span class="info-value"><code>{{ keystoreInfo?.path || config.keystore_dir }}</code></span></div>
          <div class="info-item"><span class="info-label">文件数量</span><span class="info-value">{{ keystoreInfo?.file_count ?? '-' }}</span></div>
          <div class="info-item"><span class="info-label">磁盘占用</span><span class="info-value">{{ keystoreInfo?.total_size_display ?? '-' }}</span></div>
        </div>
      </section>

      <section class="card">
        <h3 class="card-title">CA / 证书默认参数</h3>
        <div v-if="!editingParams" class="info-grid">
          <div class="info-item"><span class="info-label">CA 默认有效期</span><span class="info-value">{{ config.ca_default_validity_days }} 天</span></div>
          <div class="info-item"><span class="info-label">证书默认有效期</span><span class="info-value">{{ config.cert_default_validity_days }} 天</span></div>
          <div class="info-item"><span class="info-label">CRL 有效期</span><span class="info-value">{{ config.crl_validity_hours }} 小时</span></div>
        </div>
        <div v-else class="edit-form">
          <label>CA 默认有效期(天)<input v-model.number="editForm.ca_default_validity_days" type="number" min="1" max="36500" /></label>
          <label>证书默认有效期(天)<input v-model.number="editForm.cert_default_validity_days" type="number" min="1" max="36500" /></label>
          <label>CRL 有效期(小时)<input v-model.number="editForm.crl_validity_hours" type="number" min="1" max="8760" /></label>
        </div>
        <div class="actions">
          <button v-if="!editingParams" class="btn btn-primary" @click="startEditParams">编辑</button>
          <template v-else>
            <button class="btn btn-primary" :disabled="paramSaving" @click="saveParams">{{ paramSaving ? '保存中...' : '保存' }}</button>
            <button class="btn btn-ghost" :disabled="paramSaving" @click="editingParams = false">取消</button>
          </template>
        </div>
        <p v-if="paramMsg" class="msg">{{ paramMsg }}</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.settings h2 { margin-bottom: 1.5rem; font-size: 1.5rem; }
.loading { color: #888; font-style: italic; }
.error-msg { color: #dc3545; padding: 1rem; background: #fff; border-radius: 8px; }
.card { background: #fff; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.25rem; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.card-title { font-size: 1.05rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid #f0f0f0; }
.ca-card { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 1.5rem; align-items: start; }
.ca-editor { border-left: 1px solid #eee; padding-left: 1.5rem; min-height: 1rem; }
.ca-editor h4 { margin-bottom: 0.75rem; font-size: 0.95rem; }
.info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
.info-item { display: flex; flex-direction: column; gap: 0.25rem; }
.info-wide { grid-column: 1 / -1; }
.info-label { font-size: 0.8rem; color: #888; }
.info-value { font-size: 0.95rem; font-weight: 500; color: #1a1a2e; word-break: break-all; }
code { font-size: 0.8rem; background: #f0f0f0; padding: 0.15rem 0.4rem; border-radius: 3px; }
.badge { display: inline-block; padding: 0.2rem 0.75rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; width: fit-content; }
.badge-on { background: #d4edda; color: #155724; }
.badge-off { background: #e2e3e5; color: #383d41; }
.badge-error { background: #f8d7da; color: #721c24; }
label { display: flex; flex-direction: column; gap: 0.3rem; font-size: 0.82rem; color: #666; margin-bottom: 0.75rem; }
input, select { padding: 0.45rem 0.6rem; border: 1px solid #ccc; border-radius: 6px; font-size: 0.9rem; width: 100%; }
.edit-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
.actions { display: flex; gap: 0.5rem; margin-top: 1rem; }
.btn { padding: 0.45rem 1rem; border: none; border-radius: 6px; font-size: 0.85rem; cursor: pointer; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: #0f3460; color: #fff; }
.btn-ghost { background: transparent; color: #666; border: 1px solid #ccc; }
.msg { margin-top: 0.5rem; font-size: 0.82rem; padding: 0.35rem 0.75rem; border-radius: 6px; background: #fff3cd; color: #856404; }
.table-list { margin-top: 1rem; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.45rem 0.6rem; text-align: left; border-bottom: 1px solid #eee; font-size: 0.84rem; }
th { color: #666; font-weight: 600; }
@media (max-width: 800px) {
  .ca-card { grid-template-columns: 1fr; }
  .ca-editor { border-left: 0; padding-left: 0; border-top: 1px solid #eee; padding-top: 1rem; }
}
</style>
