import { ref } from 'vue'
import { defineStore } from 'pinia'
import { certApi } from '@/api'

interface CertItem {
  id: string
  serial_number: string
  cert_type: string
  subject_dn: string
  user_name: string
  not_after: string
  status: string
}
// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface CertDetail {}

export const useCertStore = defineStore('cert', () => {
  const certs = ref<CertItem[]>([])
  const current = ref<CertDetail | null>(null)

  async function fetchList(params?: { cert_type?: string; status?: string }) {
    const res = (await certApi.list(params)) as CertItem[]
    certs.value = res
    return certs.value
  }

  async function issue(data: Record<string, unknown>) {
    const res = await certApi.issue(data)
    await fetchList()
    return res
  }

  async function fetchDetail(serial: string) {
    current.value = (await certApi.detail(serial)) as CertDetail
    return current.value
  }

  async function checkStatus(serial: string) {
    return await certApi.status(serial)
  }

  return { certs, current, fetchList, issue, fetchDetail, checkStatus }
})
