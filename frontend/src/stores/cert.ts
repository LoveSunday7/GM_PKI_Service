import { ref } from 'vue'
import { defineStore } from 'pinia'
import { certApi } from '@/api'

export const useCertStore = defineStore('cert', () => {
  const certs = ref<any[]>([])
  const current = ref<any>(null)

  async function fetchList(params?: { cert_type?: string; status?: string }) {
    const res = await certApi.list(params)
    certs.value = res as any[]
    return certs.value
  }

  async function issue(data: Record<string, unknown>) {
    const res = await certApi.issue(data)
    await fetchList()
    return res
  }

  async function fetchDetail(serial: string) {
    current.value = await certApi.detail(serial)
    return current.value
  }

  async function checkStatus(serial: string) {
    return await certApi.status(serial)
  }

  return { certs, current, fetchList, issue, fetchDetail, checkStatus }
})
