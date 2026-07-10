<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { adminApi, type AdminUserItem } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { formatError } from '@/utils/errors'

defineOptions({ name: 'AdminUsersPage' })

const toast = useToast()
const authStore = useAuthStore()

// ── 列表状态 ───────────────────────────────────────────────────
const loading = ref(true)
const users = ref<AdminUserItem[]>([])

// ── 创建表单 ───────────────────────────────────────────────────
const creating = ref(false)
const createForm = ref({ username: '', password: '', role: 'user' })
const createError = ref('')

// ── 删除确认 ───────────────────────────────────────────────────
const deleting = ref('')

// ── 密码弹窗 ───────────────────────────────────────────────────
const pwdTarget = ref<AdminUserItem | null>(null)
const pwdForm = ref({ newPassword: '' })
const pwdSaving = ref(false)
const pwdError = ref('')

// ── 加载用户列表 ───────────────────────────────────────────────
async function loadUsers() {
  loading.value = true
  try {
    users.value = await adminApi.list()
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    loading.value = false
  }
}

onMounted(loadUsers)

// ── 创建用户 ───────────────────────────────────────────────────
async function handleCreate() {
  creating.value = true
  createError.value = ''
  try {
    const res = await adminApi.create({
      username: createForm.value.username,
      password: createForm.value.password,
      role: createForm.value.role,
    })
    toast.success(res.message)
    createForm.value = { username: '', password: '', role: 'user' }
    await loadUsers()
  } catch (e: unknown) {
    createError.value = formatError(e)
  } finally {
    creating.value = false
  }
}

// ── 删除用户 ───────────────────────────────────────────────────
async function handleDelete(username: string) {
  if (deleting.value) return
  deleting.value = username
  try {
    const res = await adminApi.delete(username)
    toast.success(res.message)
    await loadUsers()
  } catch (e: unknown) {
    toast.error(formatError(e))
  } finally {
    deleting.value = ''
  }
}

// ── 修改密码 ───────────────────────────────────────────────────
function openPwdModal(user: AdminUserItem) {
  pwdTarget.value = user
  pwdForm.value.newPassword = ''
  pwdError.value = ''
}

function closePwdModal() {
  pwdTarget.value = null
}

async function handleChangePwd() {
  if (!pwdTarget.value) return
  pwdSaving.value = true
  pwdError.value = ''
  try {
    const res = await adminApi.changePassword(pwdTarget.value.username, pwdForm.value.newPassword)
    toast.success(res.message)
    closePwdModal()
  } catch (e: unknown) {
    pwdError.value = formatError(e)
  } finally {
    pwdSaving.value = false
  }
}
</script>

<template>
  <div class="admin-users">
    <h2>账户管理</h2>

    <!-- ── 新增管理员表单 ──────────────────────────────────── -->
    <section class="card">
      <h3 class="card-title">新增账户</h3>
      <div class="create-form">
        <div class="form-row">
          <label>
            <span>用户名</span>
            <input v-model="createForm.username" placeholder="输入用户名" maxlength="64" />
          </label>
          <label>
            <span>密码</span>
            <input v-model="createForm.password" type="password" placeholder="至少 6 位" maxlength="128" />
          </label>
          <label>
            <span>角色</span>
            <select v-model="createForm.role">
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </label>
          <button class="btn btn-primary" :disabled="creating || !createForm.username || !createForm.password" @click="handleCreate">
            {{ creating ? '⏳ 创建中...' : '创建' }}
          </button>
        </div>
        <p v-if="createError" class="msg msg-err">{{ createError }}</p>
      </div>
    </section>

    <!-- ── 用户列表 ────────────────────────────────────────── -->
    <section class="card">
      <h3 class="card-title">📋 用户列表</h3>

      <!-- 骨架屏 -->
      <div v-if="loading" class="skeleton-table">
        <div v-for="i in 3" :key="i" class="skeleton-row">
          <div class="skeleton skeleton-cell" style="width:20%" />
          <div class="skeleton skeleton-cell" style="width:12%" />
          <div class="skeleton skeleton-cell" style="width:22%" />
          <div class="skeleton skeleton-cell" style="width:15%" />
        </div>
      </div>
      <template v-else-if="users.length">
      <div class="responsive-table">
      <table class="table">
        <thead>
          <tr>
            <th>用户名</th>
            <th>角色</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td data-label="用户名">
              <span class="username">{{ u.username }}</span>
              <span v-if="u.username === authStore.username" class="tag-me">我</span>
            </td>
            <td data-label="角色">
              <span :class="['badge', 'badge-' + u.role]">{{ u.role }}</span>
            </td>
            <td data-label="创建时间">{{ new Date(u.created_at).toLocaleString() }}</td>
            <td data-label="操作" class="actions">
              <button class="btn btn-sm btn-outline" @click="openPwdModal(u)">🔑 改密</button>
              <button
                class="btn btn-sm btn-danger"
                :disabled="deleting === u.username"
                @click="handleDelete(u.username)"
              >
                {{ deleting === u.username ? '⏳' : '🗑️ 删除' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      </div>
      </template>
      <div v-else class="empty-state">
        <div class="empty-icon">👥</div>
        <div class="empty-title">暂无账户</div>
        <div class="empty-hint">请在上方填写信息创建账户</div>
      </div>
    </section>

    <!-- ── 修改密码弹窗 ────────────────────────────────────── -->
    <div v-if="pwdTarget" class="modal-overlay" @click.self="closePwdModal">
      <div class="modal">
        <h3>🔑 修改密码</h3>
        <p class="modal-sub">用户: <strong>{{ pwdTarget.username }}</strong> ({{ pwdTarget.role }})</p>

        <div class="modal-body">
          <label>
            <span>新密码</span>
            <input v-model="pwdForm.newPassword" type="password" placeholder="至少 6 位" maxlength="128" @keyup.enter="handleChangePwd" />
          </label>
          <p v-if="pwdError" class="msg msg-err">{{ pwdError }}</p>
        </div>

        <div class="modal-actions">
          <button class="btn btn-primary" :disabled="pwdSaving || pwdForm.newPassword.length < 6" @click="handleChangePwd">
            {{ pwdSaving ? '⏳ 保存中...' : '💾 保存' }}
          </button>
          <button class="btn btn-ghost" :disabled="pwdSaving" @click="closePwdModal">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-users h2 { margin-bottom: 1.5rem; font-size: 1.5rem; }

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

/* ── 创建表单 ──────────────────────────────────────── */
.form-row {
  display: flex;
  gap: 0.75rem;
  align-items: flex-end;
  flex-wrap: wrap;
}
.form-row label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8rem;
  color: #888;
}
.form-row input, .form-row select {
  padding: 0.45rem 0.6rem;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 0.9rem;
  min-width: 140px;
}
.form-row input:focus, .form-row select:focus {
  outline: none;
  border-color: #0f3460;
  box-shadow: 0 0 0 2px rgba(15, 52, 96, 0.15);
}

/* ── 表格 ──────────────────────────────────────────── */
.table { width: 100%; border-collapse: collapse; }
.table th, .table td {
  padding: 0.6rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid #eee;
  font-size: 0.88rem;
}
.table th { color: #666; font-weight: 600; font-size: 0.8rem; }
.username { font-weight: 500; }
.tag-me {
  font-size: 0.7rem;
  background: #0f3460;
  color: #fff;
  padding: 0.1rem 0.4rem;
  border-radius: 8px;
  margin-left: 0.4rem;
}
.actions { display: flex; gap: 0.4rem; }

/* ── 标记 ──────────────────────────────────────────── */
.badge {
  display: inline-block;
  padding: 0.2rem 0.65rem;
  border-radius: 20px;
  font-size: 0.78rem;
  font-weight: 600;
}
.badge-admin { background: #d4edda; color: #155724; }
.badge-user { background: #e2e3e5; color: #343a40; }
.badge-auditor { background: #d1ecf1; color: #0c5460; }
.badge-operator { background: #fff3cd; color: #856404; }

/* ── 按钮 ──────────────────────────────────────────── */
.btn {
  padding: 0.45rem 1rem;
  border: none;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-sm { padding: 0.3rem 0.65rem; font-size: 0.78rem; }
.btn-primary { background: #0f3460; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #16213e; }
.btn-outline {
  background: transparent;
  color: #0f3460;
  border: 1px solid #0f3460;
}
.btn-outline:hover:not(:disabled) { background: rgba(15, 52, 96, 0.06); }
.btn-danger {
  background: transparent;
  color: #dc3545;
  border: 1px solid #dc3545;
}
.btn-danger:hover:not(:disabled) { background: rgba(220, 53, 69, 0.08); }
.btn-ghost {
  background: transparent;
  color: #666;
  border: 1px solid #ccc;
}
.btn-ghost:hover:not(:disabled) { background: #f5f5f5; }

/* ── 消息 ──────────────────────────────────────────── */
.msg {
  margin-top: 0.5rem;
  font-size: 0.82rem;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
}
.msg-ok { background: #d4edda; color: #155724; }
.msg-err { background: #f8d7da; color: #721c24; }
.loading { color: #888; font-style: italic; }
.empty { color: #aaa; font-style: italic; text-align: center; padding: 2rem; }

/* ── 弹窗 ──────────────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.modal {
  background: #fff;
  border-radius: 12px;
  padding: 1.5rem;
  width: 380px;
  max-width: 90vw;
  box-shadow: 0 8px 32px rgba(0,0,0,0.18);
}
.modal h3 { margin-bottom: 0.35rem; }
.modal-sub { font-size: 0.85rem; color: #888; margin-bottom: 1rem; }
.modal-body { margin-bottom: 1rem; }
.modal-body label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8rem;
  color: #888;
}
.modal-body input {
  padding: 0.45rem 0.6rem;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 0.9rem;
}
.modal-body input:focus {
  outline: none;
  border-color: #0f3460;
  box-shadow: 0 0 0 2px rgba(15, 52, 96, 0.15);
}
.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
</style>
