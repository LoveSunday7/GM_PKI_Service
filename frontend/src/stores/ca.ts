import { ref } from 'vue'
import { defineStore } from 'pinia'
import { caApi } from '@/api'

export const useCAStore = defineStore('ca', () => {
  const initialized = ref(false)
  const caName = ref('')
  const rootCerts = ref<any[]>([])

  async function fetchStatus() {
    const res = await caApi.status()
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
    rootCerts.value = res as any[]
    return rootCerts.value
  }

  return { initialized, caName, rootCerts, fetchStatus, initialize, fetchRootCerts }
})
