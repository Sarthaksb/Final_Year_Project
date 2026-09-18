/**
 * frontend/src/api/client.ts
 * Shared Axios instance for all API calls.
 *
 * Features:
 *  - Baseurl = /api (proxied by Vite to localhost:8000 in dev)
 *  - Attaches JWT Bearer token to every request automatically
 *  - Auto-logout on 401 (expired/invalid token)
 *  - Logs X-Request-ID from server responses for debugging
 *  - Extracts structured error detail from FastAPI error responses
 */

import axios, { AxiosError } from 'axios'
import { useAuthStore } from '../store'

const client = axios.create({
  baseURL: '/api',
  timeout: 30_000,
})

// ── Request: attach JWT ───────────────────────────────────────────────────────
client.interceptors.request.use(config => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response: handle auth errors + normalize error messages ───────────────────
client.interceptors.response.use(
  res => res,
  (err: AxiosError<{ detail?: string | { msg: string }[] }>) => {
    // Log request ID for server-side trace correlation
    const requestId = err.response?.headers?.['x-request-id']
    if (requestId) {
      console.debug(`[DermaAI] Request ID: ${requestId}`)
    }

    // Auto-logout on 401
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
      return Promise.reject(err)
    }

    // Normalize FastAPI validation errors into a single readable string
    const detail = err.response?.data?.detail
    if (Array.isArray(detail)) {
      // Pydantic validation error array — pick first message
      const msg = detail[0]?.msg ?? 'Validation error'
      err.message = msg
    } else if (typeof detail === 'string') {
      err.message = detail
    }

    return Promise.reject(err)
  }
)

export default client

/**
 * Helper: extract a human-readable error string from any Axios error.
 * Use this in catch blocks instead of err.message directly.
 *
 * @example
 *   catch (err) { toast.error(getErrorMessage(err)) }
 */
export function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred.'
}
