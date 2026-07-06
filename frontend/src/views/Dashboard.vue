<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

defineOptions({ name: 'DashboardPage' })

import { useCAStore } from '@/stores/ca'
import { useCertStore } from '@/stores/cert'
import { useCRLStore } from '@/stores/crl'

const caStore = useCAStore()
const certStore = useCertStore()
const crlStore = useCRLStore()

const loading = ref(true)

onMounted(async () => {
  await Promise.all([
    caStore.fetchStatus().catch(() => {}),
    certStore.fetchList().catch(() => {}),
    crlStore.fetchCurrent().catch(() => {}),
  ])
  loading.value = false
})

// ── 统计计算 ──────────────────────────────────────────────────

const activeCerts = computed(() => certStore.certs.filter((c: { status: string }) => c.status === 'active'))
const revokedCerts = computed(() => certStore.certs.filter((c: { status: string }) => c.status === 'revoked'))
const signCerts = computed(() => certStore.certs.filter((c: { cert_type: string }) => c.cert_type === 'sign'))
const encryptCerts = computed(() => certStore.certs.filter((c: { cert_type: string }) => c.cert_type === 'encrypt'))

// 即将过期的证书（30 天内）
const expiringSoon = computed(() => {
  const threshold = new Date()
  threshold.setDate(threshold.getDate() + 30)
  return activeCerts.value.filter((c: { not_after: string }) => new Date(c.not_after) <= threshold)
})

const revokedCount = computed(() => crlStore.currentCRL?.revoked_count ?? revokedCerts.value.length)
</script>

<template>
  <div class="dashboard">
    <h2>系统概览</h2>

    <div v-if="loading" class="loading">加载中...</div>

    <template v-else>
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
            <p class="count">{{ certStore.certs.length }}</p>
            <p class="sub">已签发证书</p>
          </div>
        </div>

        <div class="card card-ok">
          <div class="card-icon">✅</div>
          <div class="card-body">
            <h3>有效证书</h3>
            <p class="count">{{ activeCerts.length }}</p>
            <p class="sub">状态为 active</p>
          </div>
        </div>

        <div class="card card-warn">
          <div class="card-icon">🚫</div>
          <div class="card-body">
            <h3>已撤销</h3>
            <p class="count">{{ revokedCount }}</p>
            <p class="sub">撤销证书数</p>
          </div>
        </div>

        <div class="card" v-if="expiringSoon.length">
          <div class="card-icon">⚠️</div>
          <div class="card-body">
            <h3>即将过期</h3>
            <p class="count" style="color:#e65100">{{ expiringSoon.length }}</p>
            <p class="sub">30 天内到期</p>
          </div>
        </div>
      </div>

      <!-- 证书类型分布 & 过期预警 -->
      <div class="row">
        <section class="section">
          <h3>证书类型分布</h3>
          <div class="stat-grid" v-if="certStore.certs.length">
            <div class="stat-item">
              <span class="stat-num">{{ signCerts.length }}</span>
              <span class="stat-label">签名证书</span>
            </div>
            <div class="stat-item">
              <span class="stat-num">{{ encryptCerts.length }}</span>
              <span class="stat-label">加密证书</span>
            </div>
            <div class="stat-item">
              <span class="stat-num">{{ revokedCerts.length }}</span>
              <span class="stat-label">已撤销</span>
            </div>
          </div>
          <p v-else class="empty">暂无数据</p>
        </section>

        <section class="section">
          <h3>即将过期证书</h3>
          <table v-if="expiringSoon.length">
            <thead>
              <tr><th>序列号</th><th>用户</th><th>到期日期</th></tr>
            </thead>
            <tbody>
              <tr v-for="c in expiringSoon.slice(0, 5)" :key="c.id">
                <td><code>{{ (c as { serial_number: string }).serial_number?.slice(0, 16) }}...</code></td>
                <td>{{ (c as { user_name: string }).user_name }}</td>
                <td>{{ new Date((c as { not_after: string }).not_after).toLocaleDateString() }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else class="ok-text">暂无即将过期的证书 ✅</p>
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
.ok-text { color: #155724; }

/* ── 表格 ──────────────────────────────── */
table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
th, td { padding: 0.4rem 0.6rem; text-align: left; border-bottom: 1px solid #eee; font-size: 0.8rem; }
th { color: #666; }
code { font-size: 0.75rem; background: #f0f0f0; padding: 0.1rem 0.3rem; border-radius: 3px; }

/* ── CRL 条 ────────────────────────────── */
.crl-bar {
  display: flex; gap: 1.5rem; flex-wrap: wrap;
  font-size: 0.85rem; color: #555;
}
</style>
