/**
 * frontend/src/api/diagnosis.ts
 * Patient-facing API calls:
 *   POST /api/diagnosis/analyze   — upload image + symptoms
 *   GET  /api/cases               — paginated history
 *   GET  /api/cases/:id           — single case
 *   DELETE /api/cases/:id         — delete own case (GDPR)
 */

import client from './client'

// ── Shared types ──────────────────────────────────────────────────────────────

export interface DiagnosisResult {
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

export interface CaseOut {
  id:             string
  image_filename: string
  created_at:     string
  symptoms:       Record<string, boolean>
  result?:        DiagnosisResult
}

export interface SymptomForm {
  rapid_growth:     boolean
  bleeding:         boolean
  irregular_border: boolean
  itching:          boolean
  pain:             boolean
}

// ── Endpoints ─────────────────────────────────────────────────────────────────

/**
 * POST /api/diagnosis/analyze
 * Sends multipart/form-data: image file + symptoms JSON string.
 * Timeout raised to 90 s — the Gemini agent call can be slow.
 */
export const analyzeImage = async (
  imageFile: File,
  symptoms:  SymptomForm,
): Promise<DiagnosisResult> => {
  const form = new FormData()
  form.append('image', imageFile)
  form.append('symptoms', JSON.stringify(symptoms))
  const res = await client.post<DiagnosisResult>('/diagnosis/analyze', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 90_000,
  })
  return res.data
}

/** GET /api/cases?skip=0&limit=50 — paginated case history */
export const getCases = (skip = 0, limit = 50) =>
  client.get<CaseOut[]>('/cases', { params: { skip, limit } }).then(r => r.data)

/** GET /api/cases/:id — single case detail */
export const getCase = (caseId: string) =>
  client.get<CaseOut>(`/cases/${caseId}`).then(r => r.data)

/** DELETE /api/cases/:id — patient data erasure (204 No Content) */
export const deleteCase = (caseId: string) =>
  client.delete(`/cases/${caseId}`)
