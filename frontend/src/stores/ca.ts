import { ref } from 'vue'
import { defineStore } from 'pinia'
import { caApi } from '@/api'

interface RootCertItem {
  id: string
  serial_number: string
  subject_dn: string
  signature_algorithm: string
  not_before: string
  not_after: string
  status: string
}
interface CAStatusResponse {
  initialized: boolean
  ca_name?: string
}

export const useCAStore = defineStore('ca', () => {
  const initialized = ref(false)
  const caName = ref('')
  const rootCerts = ref<RootCertItem[]>([])

  async function fetchStatus() {
    const res = (await caApi.status()) as CAStatusResponse
    initialized.value = res.initialized
    caName.value = res.ca_name || ''
    return res
  }

  async function initialize(data: Record<string, unknown>) {
    const res = await caApi.initialize(data)
    await fetchStatus()
    return res
  }

  async function fetchRootCerts() {
    const res = await caApi.listRootCerts()
    rootCerts.value = res
    return rootCerts.value
  }

  return { initialized, caName, rootCerts, fetchStatus, initialize, fetchRootCerts }
})
