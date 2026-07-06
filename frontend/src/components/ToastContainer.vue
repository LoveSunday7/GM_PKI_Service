<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts, remove } = useToast()
</script>

<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="t in toasts"
          :key="t.id"
          :class="['toast', 'toast-' + t.type]"
          @click="remove(t.id)"
        >
          <span class="toast-icon">{{ t.type === 'success' ? '✅' : t.type === 'error' ? '❌' : 'ℹ️' }}</span>
          <span class="toast-msg">{{ t.message }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-width: 420px;
}
.toast {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
  cursor: pointer;
  font-size: 0.88rem;
  line-height: 1.4;
  backdrop-filter: blur(6px);
  transition: all 0.3s;
}
.toast-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
.toast-error   { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
.toast-info    { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
.toast-icon { flex-shrink: 0; font-size: 1rem; }
.toast-msg { flex: 1; word-break: break-word; }

/* Transition */
.toast-enter-active { transition: all 0.3s ease-out; }
.toast-leave-active { transition: all 0.2s ease-in; }
.toast-enter-from { opacity: 0; transform: translateX(60px); }
.toast-leave-to   { opacity: 0; transform: translateX(60px); }
</style>
