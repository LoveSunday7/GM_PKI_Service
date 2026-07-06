<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { certApi } from '@/api'
import { useCAStore } from '@/stores/ca'
import { useCRLStore } from '@/stores/crl'

defineOptions({ name: 'DashboardPage' })

const router = useRouter()
const caStore = useCAStore()
const crlStore = useCRLStore()

const loading = ref(true)

// ── 统计数据 ───────────────────────────────────────────────────
const stats = ref({ total: 0, active: 0, revoked: 0, sign: 0, encrypt: 0, expiring_soon: 0, today_issued: 0 })

// ── 操作时间线 ─────────────────────────────────────────────────
const activities = ref<Array<{ type: string; time: string; user: string; serial: string; detail: string }>>([])

onMounted(async () => {
  try {
    const [s, a] = await Promise.all([
      certApi.stats(),
      certApi.activity(),
      caStore.fetchStatus().catch(() => {}),
      crlStore.fetchCurrent().catch(() => {}),
    ])
    stats.value = s
    activities.value = a.activities
  } catch { /* ignore */ }
  finally { loading.value = false }
})

// ── 快捷导航 ───────────────────────────────────────────────────
function goTo(route: string) {
  router.push(route)
}

// ── 时间线图标 ─────────────────────────────────────────────────
function timelineIcon(type: string) {
  if (type === 'issue') return '📜'
  if (type === 'revoke') return '🚫'
  return '📋'
}
</script>

<template>
  <div class="dashboard">
    <h2>系统概览</h2>

    <div v-if="loading" class="loading">加载中...</div>

    <template v-else>
      <!-- 快捷操作 -->
      <div class="quick-actions">
        <button class="qa-btn qa-issue" @click="goTo('/cert')">
          <span class="qa-icon">📜</span> 签发证书
        </button>
        <button class="qa-btn qa-revoke" @click="goTo('/crl')">
          <span class="qa-icon">🚫</span> 撤销证书
        </button>
        <button class="qa-btn qa-crl" @click="goTo('/crl')">
          <span class="qa-icon">📋</span> 生成 CRL
        </button>
      </div>

      <!-- 核心指标卡片 -->
      <div class="cards">
        <div class="card card-ca">
          <div class="card-icon">🏛️</div>
          <div class="card-body">
            <h3>CA 状态</h3>
            <span :class="['badge', caStore.initialized ? 'badge-green' : 'badge-yellow']">
              {{ caStore.initialized ? '已初始化' : '未初始化' }}
            </span>
            <p v-if="caStore.caName" class="sub">{{ caStore.caName }}</p>
          </div>
        </div>

        <div class="card">
          <div class="card-icon">📜</div>
          <div class="card-body">
            <h3>证书总数</h3>
            <p class="count">{{ stats.total }}</p>
            <p class="sub">今日签发 {{ stats.today_issued }}</p>
          </div>
        </div>

        <div class="card card-ok">
          <div class="card-icon">✅</div>
          <div class="card-body">
            <h3>有效证书</h3>
            <p class="count">{{ stats.active }}</p>
            <p class="sub">状态为 active</p>
          </div>
        </div>

        <div class="card card-warn">
          <div class="card-icon">🚫</div>
          <div class="card-body">
            <h3>已撤销</h3>
            <p class="count">{{ stats.revoked }}</p>
            <p class="sub">撤销证书数</p>
          </div>
        </div>

        <div class="card" v-if="stats.expiring_soon">
          <div class="card-icon">⚠️</div>
          <div class="card-body">
            <h3>即将过期</h3>
            <p class="count" style="color:#e65100">{{ stats.expiring_soon }}</p>
            <p class="sub">30 天内到期</p>
          </div>
        </div>
      </div>

      <!-- 证书类型分布 & 操作时间线 -->
      <div class="row">
        <section class="section">
          <h3>证书类型分布</h3>
          <div class="stat-grid">
            <div class="stat-item">
              <span class="stat-num">{{ stats.sign }}</span>
              <span class="stat-label">签名证书</span>
            </div>
            <div class="stat-item">
              <span class="stat-num">{{ stats.encrypt }}</span>
              <span class="stat-label">加密证书</span>
            </div>
            <div class="stat-item">
              <span class="stat-num">{{ stats.revoked }}</span>
              <span class="stat-label">已撤销</span>
            </div>
          </div>
        </section>

        <section class="section">
          <h3>最近操作时间线</h3>
          <div v-if="activities.length" class="timeline">
            <div v-for="a in activities" :key="a.serial + a.type" class="tl-item">
              <span class="tl-icon">{{ timelineIcon(a.type) }}</span>
              <div class="tl-body">
                <span class="tl-text">{{ a.detail }}</span>
                <span class="tl-time">{{ new Date(a.time).toLocaleString() }}</span>
              </div>
            </div>
          </div>
          <p v-else class="empty">暂无操作记录</p>
        </section>
      </div>

      <!-- CRL 状态 -->
      <section class="section" v-if="crlStore.currentCRL?.crl_number">
        <h3>当前 CRL 信息</h3>
        <div class="crl-bar">
          <span>CRL #{{ crlStore.currentCRL.crl_number }}</span>
          <span>更新: {{ new Date(crlStore.currentCRL.this_update).toLocaleString() }}</span>
          <span>下次更新: {{ new Date(crlStore.currentCRL.next_update).toLocaleString() }}</span>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.dashboard h2 { margin-bottom: 1.5rem; font-size: 1.5rem; }
.loading { color: #888; font-style: italic; }

/* ── 快捷操作 ──────────────────────────── */
.quick-actions {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
}
.qa-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.6rem 1.2rem;
  border: none;
  border-radius: 10px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  color: #fff;
}
.qa-icon { font-size: 1.1rem; }
.qa-issue { background: #0f3460; }
.qa-issue:hover { background: #16213e; }
.qa-revoke { background: #dc3545; }
.qa-revoke:hover { background: #c82333; }
.qa-crl { background: #6f42c1; }
.qa-crl:hover { background: #5a32a0; }

/* ── 卡片 ──────────────────────────────── */
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 1.25rem;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  display: flex;
  gap: 1rem;
  align-items: center;
}
.card-icon { font-size: 2rem; flex-shrink: 0; }
.card-body { flex: 1; }
.card h3 { font-size: 0.85rem; color: #888; margin-bottom: 0.25rem; }
.count { font-size: 1.8rem; font-weight: 700; color: #1a1a2e; }
.sub { font-size: 0.8rem; color: #aaa; }
.card-ca { border-left: 4px solid #0f3460; }
.card-ok { border-left: 4px solid #28a745; }
.card-warn { border-left: 4px solid #dc3545; }

.badge { padding: 0.2rem 0.75rem; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
.badge-green { background: #d4edda; color: #155724; }
.badge-yellow { background: #fff3cd; color: #856404; }

/* ── 双栏 ──────────────────────────────── */
.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1.5rem;
}
@media (max-width: 768px) { .row { grid-template-columns: 1fr; } }

.section {
  background: #fff;
  border-radius: 12px;
  padding: 1.25rem;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.section h3 { margin-bottom: 0.75rem; font-size: 1rem; }

.stat-grid { display: flex; gap: 1.5rem; }
.stat-item { display: flex; flex-direction: column; align-items: center; }
.stat-num { font-size: 1.5rem; font-weight: 700; color: #1a1a2e; }
.stat-label { font-size: 0.8rem; color: #888; }

.empty { color: #888; font-style: italic; }

/* ── 时间线 ────────────────────────────── */
.timeline {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 320px;
  overflow-y: auto;
}
.tl-item {
  display: flex;
  gap: 0.5rem;
  padding: 0.35rem 0;
  border-bottom: 1px solid #f5f5f5;
}
.tl-icon { font-size: 0.9rem; flex-shrink: 0; }
.tl-body {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}
.tl-text { font-size: 0.82rem; color: #333; }
.tl-time { font-size: 0.7rem; color: #999; }

/* ── CRL 条 ────────────────────────────── */
.crl-bar {
  display: flex; gap: 1.5rem; flex-wrap: wrap;
  font-size: 0.85rem; color: #555;
}
</style>
