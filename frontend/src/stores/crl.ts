import { ref } from 'vue'
import { defineStore } from 'pinia'
import { crlApi } from '@/api'

interface CRLInfo {
  crl_number: number
  issuer_dn: string
  this_update: string
  next_update: string
  signature_algorithm: string
  revoked_count: number
  crl_pem: string
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

  async function applyRevocation(data: { cert_serial_number: string; reason: string; description?: string }) {
    return await crlApi.applyRevocation(data)
  }

  async function generate() {
    return await crlApi.generate()
  }

  async function fetchCurrent() {
    const data = await crlApi.current()
    if ('crl_number' in data && data.crl_number) {
      currentCRL.value = data as unknown as CRLInfo
    } else {
      currentCRL.value = null
    }
    return currentCRL.value
  }

  return { currentCRL, revoke, applyRevocation, generate, fetchCurrent }
})
