/**
 * frontend/src/api/doctor.ts
 * Doctor dashboard API calls — all require Bearer token with role=doctor
 *
 *   GET  /api/doctor/stats               — dashboard summary counts
 *   GET  /api/doctor/cases               — paginated + filtered case list
 *   GET  /api/doctor/cases/:id           — case detail
 *   POST /api/doctor/cases/:id/review    — submit accept/override
 *   GET  /api/doctor/cases/:id/report    — trigger PDF download
 */

import client from './client'

// ── Shared types ──────────────────────────────────────────────────────────────

export interface ReviewOut {
  doctor_id:      string
  doctor_name:    string
  decision:       'accepted' | 'overridden'
  override_class?: string
  notes?:         string
  reviewed_at:    string
}

export interface DiagnosisOut {
  predicted_class:   string
  description:       string
  confidence:        number
  is_high_risk:      boolean
  all_probabilities: Record<string, number>
  urgency:           'HIGH' | 'MEDIUM' | 'LOW'
  urgency_reasons:   string[]
  urgency_score:     number
  agent_status?:     string
  agent_result?:     Record<string, unknown>
  rag_explanation?:  string
  rag_source?:       string
  gradcam_path?:     string
}

export interface DoctorCaseOut {
  id:             string
  user_id:        string
  image_filename: string
  created_at:     string
  symptoms:       Record<string, boolean>
  result?:        DiagnosisOut
  doctor_review?: ReviewOut
}

export interface ReviewRequest {
  decision:        'accepted' | 'overridden'
  override_class?: string
  notes?:          string
}

export interface DashboardStats {
  total:          number
  high:           number
  medium:         number
  low:            number
  reviewed:       number
  pending_review: number
}

// ── Endpoints ─────────────────────────────────────────────────────────────────

/** GET /api/doctor/stats — aggregate counts for the dashboard header */
export const getDoctorStats = (): Promise<DashboardStats> =>
  client.get<DashboardStats>('/doctor/stats').then(r => r.data)

/** GET /api/doctor/cases?urgency=HIGH&skip=0&limit=50 */
export const getDoctorCases = (
  opts: { urgency?: string; skip?: number; limit?: number } = {},
) =>
  client
    .get<DoctorCaseOut[]>('/doctor/cases', {
      params: {
        ...(opts.urgency ? { urgency: opts.urgency } : {}),
        skip:  opts.skip  ?? 0,
        limit: opts.limit ?? 50,
      },
    })
    .then(r => r.data)

/** GET /api/doctor/cases/:id — full case detail */
export const getDoctorCase = (caseId: string) =>
  client.get<DoctorCaseOut>(`/doctor/cases/${caseId}`).then(r => r.data)

/** POST /api/doctor/cases/:id/review */
export const submitReview = (caseId: string, body: ReviewRequest) =>
  client.post<DoctorCaseOut>(`/doctor/cases/${caseId}/review`, body).then(r => r.data)

/** GET /api/doctor/cases/:id/report — streams PDF, triggers browser download */
export const downloadReport = async (caseId: string): Promise<void> => {
  const res = await client.get(`/doctor/cases/${caseId}/report`, {
    responseType: 'blob',
  })
  const url  = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
  const link = document.createElement('a')
  link.href  = url
  link.setAttribute('download', `dermaai_case_${caseId.slice(0, 8)}.pdf`)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
