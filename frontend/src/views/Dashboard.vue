<script setup lang="ts">
import { onMounted, ref } from 'vue'
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
</script>

<template>
  <div class="dashboard">
    <h2>仪表盘</h2>
    <div class="cards" v-if="!loading">
      <div class="card">
        <h3>CA 状态</h3>
        <p>
          <span :class="['badge', caStore.initialized ? 'badge-green' : 'badge-yellow']">
            {{ caStore.initialized ? '已初始化' : '未初始化' }}
          </span>
        </p>
        <p v-if="caStore.caName" class="sub">{{ caStore.caName }}</p>
      </div>
      <div class="card">
        <h3>用户证书</h3>
        <p class="count">{{ certStore.certs.length }}</p>
        <p class="sub">已签发</p>
      </div>
      <div class="card">
        <h3>已撤销</h3>
        <p class="count">{{ crlStore.currentCRL?.revoked_count ?? 0 }}</p>
        <p class="sub">证书</p>
      </div>
    </div>
    <p v-else class="loading">加载中...</p>
  </div>
</template>

<style scoped>
.dashboard h2 {
  margin-bottom: 1.5rem;
  font-size: 1.5rem;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.25rem;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
.card h3 {
  font-size: 0.9rem;
  color: #666;
  margin-bottom: 0.5rem;
}
.count {
  font-size: 2rem;
  font-weight: 700;
  color: #1a1a2e;
}
.sub {
  font-size: 0.85rem;
  color: #888;
  margin-top: 0.25rem;
}
.badge {
  padding: 0.2rem 0.75rem;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 600;
}
.badge-green {
  background: #d4edda;
  color: #155724;
}
.badge-yellow {
  background: #fff3cd;
  color: #856404;
}
.loading {
  color: #888;
  font-style: italic;
}
</style>
