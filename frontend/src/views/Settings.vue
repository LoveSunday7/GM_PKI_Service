<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { systemApi, type DatabaseInfo, type KeystoreInfo, type LogQueryResponse, type SystemConfig } from '@/api'

defineOptions({ name: 'SettingsPage' })

// ── 状态 ───────────────────────────────────────────────────────
const loading = ref(true)
const config = ref<SystemConfig | null>(null)
const keystoreInfo = ref<KeystoreInfo | null>(null)
const dbInfo = ref<DatabaseInfo | null>(null)
const error = ref('')

// ── 日志查看 ───────────────────────────────────────────────────
const LOG_FILTER_LEVELS = ['', 'DEBUG', 'INFO', 'WARNING', 'ERROR']
const logData = ref<LogQueryResponse | null>(null)
const logLines = ref(100)
const logLevel = ref('')
const logLoading = ref(false)
const logError = ref('')

// ── 日志级别 ───────────────────────────────────────────────────
const LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
const logLevelSaving = ref(false)
const logLevelMsg = ref('')

// ── 证书参数编辑 ───────────────────────────────────────────────
const editingParams = ref(false)
const paramSaving = ref(false)
const paramMsg = ref('')
const editForm = ref({
  ca_default_validity_days: 0,
  cert_default_validity_days: 0,
  crl_validity_hours: 0,
})

// ── 加载数据 ───────────────────────────────────────────────────
onMounted(async () => {
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
})

// ── 修改日志级别 ───────────────────────────────────────────────
async function changeLogLevel(level: string) {
  logLevelSaving.value = true
  logLevelMsg.value = ''
  try {
    const res = await systemApi.updateLogLevel(level)
    if (config.value) config.value.log_level = res.current_level
    logLevelMsg.value = res.message
    setTimeout(() => { logLevelMsg.value = '' }, 3000)
  } catch (e: unknown) {
    logLevelMsg.value = e instanceof Error ? e.message : '修改失败'
  } finally {
    logLevelSaving.value = false
  }
}

// ── 编辑证书参数 ───────────────────────────────────────────────
function startEditParams() {
  if (!config.value) return
  editForm.value = {
    ca_default_validity_days: config.value.ca_default_validity_days,
    cert_default_validity_days: config.value.cert_default_validity_days,
    crl_validity_hours: config.value.crl_validity_hours,
  }
  editingParams.value = true
}

function cancelEditParams() {
  editingParams.value = false
  paramMsg.value = ''
}

async function saveParams() {
  paramSaving.value = true
  paramMsg.value = ''
  try {
    const res = await systemApi.updateConfig({
      ca_default_validity_days: editForm.value.ca_default_validity_days,
      cert_default_validity_days: editForm.value.cert_default_validity_days,
      crl_validity_hours: editForm.value.crl_validity_hours,
    })
    if (config.value) {
      config.value.ca_default_validity_days = res.ca_default_validity_days
      config.value.cert_default_validity_days = res.cert_default_validity_days
      config.value.crl_validity_hours = res.crl_validity_hours
    }
    paramMsg.value = res.message
    editingParams.value = false
    setTimeout(() => { paramMsg.value = '' }, 3000)
  } catch (e: unknown) {
    paramMsg.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    paramSaving.value = false
  }
}

// ── 日志查看 ───────────────────────────────────────────────────
async function fetchLogs() {
  logLoading.value = true
  logError.value = ''
  try {
    const params: { lines?: number; level?: string } = { lines: logLines.value }
    if (logLevel.value) params.level = logLevel.value
    logData.value = await systemApi.getLogs(params)
  } catch (e: unknown) {
    logError.value = e instanceof Error ? e.message : '加载日志失败'
    logData.value = null
  } finally {
    logLoading.value = false
  }
}

function handleDownloadLogs() {
  systemApi.downloadLogs().catch(e => {
    logError.value = e instanceof Error ? e.message : '下载失败'
  })
}
</script>

<template>
  <div class="settings">
    <h2>⚙️ 系统设置</h2>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else-if="config">
      <!-- ── 应用信息卡片 ────────────────────────────────── -->
      <section class="card">
        <h3 class="card-title">📋 应用信息</h3>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">应用名称</span>
            <span class="info-value">{{ config.app_name }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">版本</span>
            <span class="info-value">v1.0.0</span>
          </div>
          <div class="info-item">
            <span class="info-label">调试模式</span>
            <span :class="['badge', config.debug ? 'badge-on' : 'badge-off']">
              {{ config.debug ? '开启' : '关闭' }}
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">数据库后端</span>
            <span class="info-value">{{ config.database_type.toUpperCase() }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">签名算法</span>
            <span class="info-value"><code>{{ config.default_signature_algorithm }}</code></span>
          </div>
        </div>
      </section>

      <!-- ── 数据库信息卡片 ──────────────────────────────── -->
      <section class="card">
        <h3 class="card-title">🗄️ 数据库信息</h3>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">数据库类型</span>
            <span class="info-value">{{ dbInfo?.database_type?.toUpperCase() ?? '-' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">连接状态</span>
            <span :class="['badge', dbInfo?.connected ? 'badge-on' : 'badge-error']">
              {{ dbInfo?.connected ? '已连接' : '已断开' }}
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">数据表数量</span>
            <span class="info-value">{{ dbInfo?.tables.length ?? '-' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">总行数</span>
            <span class="info-value">{{ dbInfo?.total_rows ?? '-' }}</span>
          </div>
        </div>
        <!-- 表详情列表 -->
        <div v-if="dbInfo?.tables.length" class="file-list">
          <h4>表详情</h4>
          <table>
            <thead>
              <tr><th>表名</th><th>行数</th></tr>
            </thead>
            <tbody>
              <tr v-for="t in dbInfo.tables" :key="t.name">
                <td><code>{{ t.name }}</code></td>
                <td>{{ t.row_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- ── 密钥库信息卡片 ──────────────────────────────── -->
      <section class="card">
        <h3 class="card-title">🔑 密钥库信息</h3>
        <div class="info-grid">
          <div class="info-item info-wide">
            <span class="info-label">存储路径</span>
            <span class="info-value"><code>{{ keystoreInfo?.path || config.keystore_dir }}</code></span>
          </div>
          <div class="info-item">
            <span class="info-label">文件数量</span>
            <span class="info-value">{{ keystoreInfo?.file_count ?? '-' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">磁盘占用</span>
            <span class="info-value">{{ keystoreInfo?.total_size_display ?? '-' }}</span>
          </div>
        </div>
        <!-- 文件列表 -->
        <div v-if="keystoreInfo?.files.length" class="file-list">
          <h4>文件清单</h4>
          <table>
            <thead>
              <tr><th>文件名</th><th>大小</th></tr>
            </thead>
            <tbody>
              <tr v-for="f in keystoreInfo.files" :key="f.name">
                <td><code>{{ f.name }}</code></td>
                <td>{{ f.size_display }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- ── 日志配置卡片 ────────────────────────────────── -->
      <section class="card">
        <h3 class="card-title">📝 日志配置</h3>
        <div class="log-row">
          <span class="info-label">当前级别</span>
          <span :class="['badge', 'badge-' + config.log_level.toLowerCase()]">
            {{ config.log_level }}
          </span>
          <div class="level-select">
            <select
              :value="config.log_level"
              :disabled="logLevelSaving"
              @change="changeLogLevel(($event.target as HTMLSelectElement).value)"
            >
              <option v-for="lv in LOG_LEVELS" :key="lv" :value="lv">{{ lv }}</option>
            </select>
            <span v-if="logLevelSaving" class="hint">⏳ 切换中...</span>
          </div>
        </div>
        <p v-if="logLevelMsg" class="msg" :class="{ 'msg-ok': logLevelMsg.includes('已'), 'msg-warn': !logLevelMsg.includes('已') }">
          {{ logLevelMsg }}
        </p>
      </section>

      <!-- ── CA/证书默认参数卡片 ──────────────────────────── -->
      <section class="card">
        <h3 class="card-title">📐 CA / 证书默认参数</h3>

        <!-- 查看模式 -->
        <div v-if="!editingParams" class="info-grid">
          <div class="info-item">
            <span class="info-label">CA 默认有效期</span>
            <span class="info-value">{{ config.ca_default_validity_days }} 天</span>
          </div>
          <div class="info-item">
            <span class="info-label">证书默认有效期</span>
            <span class="info-value">{{ config.cert_default_validity_days }} 天</span>
          </div>
          <div class="info-item">
            <span class="info-label">CRL 有效期</span>
            <span class="info-value">{{ config.crl_validity_hours }} 小时</span>
          </div>
        </div>

        <!-- 编辑模式 -->
        <div v-else class="edit-form">
          <div class="form-field">
            <label>CA 默认有效期（天）</label>
            <input v-model.number="editForm.ca_default_validity_days" type="number" min="1" max="36500" />
          </div>
          <div class="form-field">
            <label>证书默认有效期（天）</label>
            <input v-model.number="editForm.cert_default_validity_days" type="number" min="1" max="36500" />
          </div>
          <div class="form-field">
            <label>CRL 有效期（小时）</label>
            <input v-model.number="editForm.crl_validity_hours" type="number" min="1" max="8760" />
          </div>
        </div>

        <div class="param-actions">
          <template v-if="!editingParams">
            <button class="btn btn-primary" @click="startEditParams">✏️ 编辑</button>
          </template>
          <template v-else>
            <button class="btn btn-primary" :disabled="paramSaving" @click="saveParams">
              {{ paramSaving ? '⏳ 保存中...' : '💾 保存' }}
            </button>
            <button class="btn btn-ghost" :disabled="paramSaving" @click="cancelEditParams">取消</button>
          </template>
        </div>
        <p v-if="paramMsg" class="msg" :class="{ 'msg-ok': paramMsg.includes('已更新'), 'msg-warn': !paramMsg.includes('已更新') }">
          {{ paramMsg }}
        </p>
      </section>

      <!-- ── 日志查看卡片 ────────────────────────────────── -->
      <section class="card">
        <h3 class="card-title">📄 日志查看</h3>
        <!-- 工具栏 -->
        <div class="log-toolbar">
          <div class="toolbar-left">
            <label class="toolbar-label">
              行数
              <input v-model.number="logLines" type="number" min="1" max="10000" class="toolbar-input-num" />
            </label>
            <label class="toolbar-label">
              级别
              <select v-model="logLevel" class="toolbar-select">
                <option v-for="lv in LOG_FILTER_LEVELS" :key="lv" :value="lv">
                  {{ lv || '全部' }}
                </option>
              </select>
            </label>
            <button class="btn btn-sm btn-primary" :disabled="logLoading" @click="fetchLogs">
              {{ logLoading ? '⏳ 查询中...' : '🔍 查询' }}
            </button>
          </div>
          <div class="toolbar-right">
            <button class="btn btn-sm btn-outline" @click="handleDownloadLogs">⬇️ 下载完整日志</button>
          </div>
        </div>

        <!-- 状态信息 -->
        <div v-if="logData" class="log-stats">
          <span>文件: <code>{{ logData.log_file.split('/').pop() }}</code></span>
          <span>总行数: {{ logData.total_lines }}</span>
          <span>显示: {{ logData.lines.length }} 行</span>
          <span v-if="logData.level_filter">级别过滤: {{ logData.level_filter }}</span>
        </div>

        <!-- 日志内容 -->
        <div v-if="logError" class="log-error">{{ logError }}</div>
        <pre v-else-if="logData" class="log-viewer"><code>{{ logData.lines.join('\n') || '(空)' }}</code></pre>
        <p v-else class="log-placeholder">点击"查询"加载日志</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.settings h2 { margin-bottom: 1.5rem; font-size: 1.5rem; }
.loading { color: #888; font-style: italic; }
.error-msg { color: #dc3545; padding: 1rem; background: #fff; border-radius: 8px; }

/* ── 卡片 ──────────────────────────────────────────── */
.card {
  background: #fff;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1.25rem;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.card-title {
  font-size: 1.05rem;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #f0f0f0;
}

/* ── 信息网格 ──────────────────────────────────────── */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.info-wide {
  grid-column: 1 / -1;
}
.info-label {
  font-size: 0.8rem;
  color: #888;
}
.info-value {
  font-size: 0.95rem;
  font-weight: 500;
  color: #1a1a2e;
}
.info-value code {
  font-size: 0.8rem;
  background: #f0f0f0;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  word-break: break-all;
}

/* ── 标记 ──────────────────────────────────────────── */
.badge {
  display: inline-block;
  padding: 0.2rem 0.75rem;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 600;
  width: fit-content;
}
.badge-on { background: #d4edda; color: #155724; }
.badge-off { background: #e2e3e5; color: #383d41; }
.badge-debug { background: #d1ecf1; color: #0c5460; }
.badge-info { background: #d4edda; color: #155724; }
.badge-warning { background: #fff3cd; color: #856404; }
.badge-error { background: #f8d7da; color: #721c24; }

/* ── 文件列表 ──────────────────────────────────────── */
.file-list { margin-top: 1rem; }
.file-list h4 { font-size: 0.85rem; color: #888; margin-bottom: 0.5rem; }
.file-list table { width: 100%; border-collapse: collapse; }
.file-list th, .file-list td {
  padding: 0.35rem 0.6rem;
  text-align: left;
  border-bottom: 1px solid #eee;
  font-size: 0.82rem;
}
.file-list th { color: #666; font-weight: 600; }

/* ── 日志级别选择 ──────────────────────────────────── */
.log-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}
.level-select {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.level-select select {
  padding: 0.4rem 0.75rem;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 0.9rem;
  background: #fff;
  cursor: pointer;
}
.hint {
  font-size: 0.8rem;
  color: #888;
}

/* ── 编辑表单 ──────────────────────────────────────── */
.edit-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}
.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.form-field label {
  font-size: 0.8rem;
  color: #888;
}
.form-field input {
  padding: 0.45rem 0.6rem;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 0.9rem;
  width: 100%;
}
.form-field input:focus {
  outline: none;
  border-color: #0f3460;
  box-shadow: 0 0 0 2px rgba(15, 52, 96, 0.15);
}

/* ── 按钮 ──────────────────────────────────────────── */
.param-actions {
  display: flex;
  gap: 0.5rem;
}
.btn {
  padding: 0.45rem 1rem;
  border: none;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary {
  background: #0f3460;
  color: #fff;
}
.btn-primary:hover:not(:disabled) { background: #16213e; }
.btn-ghost {
  background: transparent;
  color: #666;
  border: 1px solid #ccc;
}
.btn-ghost:hover:not(:disabled) { background: #f5f5f5; }

/* ── 消息提示 ──────────────────────────────────────── */
.msg {
  margin-top: 0.5rem;
  font-size: 0.82rem;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
}
.msg-ok { background: #d4edda; color: #155724; }
.msg-warn { background: #fff3cd; color: #856404; }

/* ── 日志查看 ──────────────────────────────────────── */
.log-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.toolbar-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.82rem;
  color: #666;
}
.toolbar-input-num {
  width: 70px;
  padding: 0.3rem 0.4rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 0.85rem;
}
.toolbar-select {
  padding: 0.3rem 0.4rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 0.85rem;
  background: #fff;
}
.btn-sm {
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-sm:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-outline {
  background: transparent;
  color: #0f3460;
  border: 1px solid #0f3460;
}
.btn-outline:hover { background: rgba(15, 52, 96, 0.06); }

.log-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  font-size: 0.78rem;
  color: #888;
  margin-bottom: 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #f0f0f0;
}
.log-stats code { font-size: 0.75rem; }

.log-error {
  color: #dc3545;
  font-size: 0.85rem;
  padding: 0.5rem;
  background: #fff5f5;
  border-radius: 4px;
}

.log-viewer {
  background: #1a1a2e;
  color: #e0e0e0;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  font-size: 0.72rem;
  line-height: 1.5;
  max-height: 400px;
  overflow: auto;
  white-space: pre;
  margin: 0;
}
.log-viewer code {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: inherit;
  background: none;
  padding: 0;
}

.log-placeholder {
  color: #aaa;
  font-style: italic;
  text-align: center;
  padding: 2rem;
}
</style>
