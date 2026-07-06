import { ref } from 'vue'
import { defineStore } from 'pinia'
import { crlApi } from '@/api'

interface CRLInfo {
  crl_number: number
  issuer_dn: string
  this_update: string
  next_update: string
  revoked_count: number
  revoked_certificates: Array<{
    cert_serial_number: string
    reason: string
    revoked_at: string
  }>
}

export const useCRLStore = defineStore('crl', () => {
  const currentCRL = ref<CRLInfo | null>(null)

  async function revoke(data: { cert_serial_number: string; reason: string }) {
    return await crlApi.revoke(data)
  }

  async function generate() {
    return await crlApi.generate()
  }

  async function fetchCurrent() {
    currentCRL.value = (await crlApi.current()) as CRLInfo
    return currentCRL.value
  }

  return { currentCRL, revoke, generate, fetchCurrent }
})
