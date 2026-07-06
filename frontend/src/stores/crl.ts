import { ref } from 'vue'
import { defineStore } from 'pinia'
import { crlApi } from '@/api'

export const useCRLStore = defineStore('crl', () => {
  const currentCRL = ref<any>(null)

  async function revoke(data: { cert_serial_number: string; reason: string }) {
    return await crlApi.revoke(data)
  }

  async function generate() {
    return await crlApi.generate()
  }

  async function fetchCurrent() {
    currentCRL.value = await crlApi.current()
    return currentCRL.value
  }

  return { currentCRL, revoke, generate, fetchCurrent }
})
