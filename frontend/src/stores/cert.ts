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
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)

  async function fetchList(params?: { cert_type?: string; status?: string; page?: number; page_size?: number }) {
    const res = await certApi.list(params)
    certs.value = res.items
    total.value = res.total
    page.value = res.page
    pageSize.value = res.page_size
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

  return { certs, current, total, page, pageSize, fetchList, issue, fetchDetail, checkStatus }
})
