import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getDoctorCase,
  submitReview,
  downloadReport,
  DoctorCaseOut,
  ReviewRequest,
} from '../../api/doctor'
import { useToast } from '../../components/Toast'

const ISIC_CLASSES = ['MEL', 'NV', 'BCC', 'AK', 'BKL', 'DF', 'VASC', 'SCC']
const ISIC_LABELS: Record<string, string> = {
  MEL: 'Melanoma', NV: 'Melanocytic Nevus', BCC: 'Basal Cell Carcinoma',
  AK: 'Actinic Keratosis', BKL: 'Benign Keratosis-like', DF: 'Dermatofibroma',
  VASC: 'Vascular Lesion', SCC: 'Squamous Cell Carcinoma',
}

const URGENCY_BADGE: Record<string, { bg: string; text: string; border: string }> = {
  HIGH:   { bg: 'bg-red-50',    text: 'text-red-700',    border: 'border-red-200' },
  MEDIUM: { bg: 'bg-amber-50',  text: 'text-amber-700',  border: 'border-amber-200' },
  LOW:    { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
}

export default function CaseReview() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const toast = useToast()

  const [caseData, setCaseData] = useState<DoctorCaseOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [decision, setDecision] = useState<'accepted' | 'overridden'>('accepted')
  const [overrideClass, setOverrideClass] = useState('MEL')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)

  useEffect(() => {
    if (!caseId) return
    getDoctorCase(caseId)
      .then(data => {
        setCaseData(data)
        if (data.doctor_review) {
          setDecision(data.doctor_review.decision)
          setOverrideClass(data.doctor_review.override_class ?? 'MEL')
          setNotes(data.doctor_review.notes ?? '')
        }
      })
      .catch(() => toast.error('Case not found or access denied.'))
      .finally(() => setLoading(false))
  }, [caseId, toast])

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!caseId) return
    setSubmitting(true)
    try {
      const body: ReviewRequest = {
        decision,
        notes: notes || undefined,
        override_class: decision === 'overridden' ? overrideClass : undefined,
      }
      const updated = await submitReview(caseId, body)
      setCaseData(updated)
      toast.success('Clinical review saved successfully.')
    } catch {
      toast.error('Failed to submit review. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const handlePdfDownload = async () => {
    if (!caseId) return
    setPdfLoading(true)
    try {
      await downloadReport(caseId)
      toast.success('PDF report downloaded.')
    } catch {
      toast.error('PDF generation failed.')
    } finally {
      setPdfLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-64px)] flex items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-full border-2 border-brand-200 border-t-brand-600 animate-spin" />
          <p className="text-gray-500 text-sm font-medium">Loading clinical case...</p>
        </div>
      </div>
    )
  }

  if (!caseData) {
    return (
      <div className="min-h-[calc(100vh-64px)] flex items-center justify-center px-4 bg-gray-50">
        <div className="text-center max-w-sm bg-white rounded-2xl p-8 scale-in border border-gray-200 shadow-card">
          <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-4 border border-red-100">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-red-400">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          </div>
          <p className="text-red-600 text-lg font-bold mb-5">Access Denied</p>
          <button onClick={() => navigate('/doctor')} className="btn-primary px-6 py-2.5 rounded-xl text-sm">
            ← Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  const r = caseData?.result
  const urgency = r?.urgency ?? 'LOW'
  const ub = URGENCY_BADGE[urgency] ?? URGENCY_BADGE.LOW
  const reviewed = caseData?.doctor_review
  const activeClass = reviewed?.decision === 'overridden' && reviewed.override_class
    ? reviewed.override_class
    : r?.predicted_class

  return (
    <div className="min-h-[calc(100vh-64px)] flex flex-col bg-gray-50">

      {/* ── Sub-nav ──────────────────────────────────────────── */}
      <div className="border-b border-gray-200 bg-white px-6 py-3 sticky top-16 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/doctor')}
              className="text-gray-500 hover:text-gray-900 transition-colors text-sm font-medium flex items-center gap-1.5"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
              </svg>
              Dashboard
            </button>
            <span className="text-gray-300">/</span>
            <span className="font-mono text-sm text-gray-500">Case {caseId?.slice(0, 12)}…</span>
          </div>
          <button
            onClick={handlePdfDownload}
            disabled={pdfLoading}
            className="btn-secondary flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
          >
            {pdfLoading ? (
              <span className="w-4 h-4 rounded-full border-2 border-gray-400 border-t-transparent animate-spin" />
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
            )}
            PDF Report
          </button>
        </div>
      </div>

      <div className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-8 grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* ── LEFT: Patient Data ─────────────────────────────── */}
        <div className="lg:col-span-4 space-y-4 page-enter">

          {/* Lesion Image */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
              <span className="text-sm font-bold text-gray-900 flex items-center gap-2">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-gray-500">
                  <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>
                  <polyline points="21 15 16 10 5 21"/>
                </svg>
                Lesion Image
              </span>
              <span className="text-xs text-gray-400 font-mono truncate max-w-[100px]">{caseData?.image_filename}</span>
            </div>
            <div className="p-4 flex items-center justify-center bg-gray-50 min-h-[240px]">
              {caseData?.image_filename ? (
                <img
                  src={`/uploads/${caseData.image_filename}`}
                  alt="Skin lesion"
                  className="max-h-[280px] w-auto rounded-xl object-contain border border-gray-200 shadow-sm"
                  onError={e => {
                    (e.target as HTMLImageElement).src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300"><rect width="300" height="300" fill="%23f1f5f9"/><text x="150" y="150" fill="%2394a3b8" text-anchor="middle" dominant-baseline="middle" font-family="sans-serif" font-size="14">Image Not Found</text></svg>'
                  }}
                />
              ) : (
                <p className="text-gray-400 text-sm">No image available</p>
              )}
            </div>
          </div>

          {/* Symptoms */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-card p-5">
            <h3 className="text-sm font-bold text-gray-900 mb-4 flex items-center gap-2">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-gray-500">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
              </svg>
              Reported Symptoms
            </h3>
            <div className="space-y-2">
              {Object.entries(caseData?.symptoms ?? {}).map(([sym, val]) => (
                <div key={sym} className="flex items-center justify-between p-2.5 rounded-lg bg-gray-50 border border-gray-100">
                  <span className="text-sm text-gray-700 capitalize font-medium">
                    {sym.replace(/_/g, ' ')}
                  </span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                    val
                      ? 'bg-red-50 text-red-600 border-red-200'
                      : 'bg-gray-100 text-gray-400 border-gray-200'
                  }`}>
                    {val ? 'DETECTED' : 'NONE'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Meta */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-card p-4">
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-400">Patient ID</span>
                <span className="text-gray-800 font-mono text-[11px]">{caseData?.user_id?.slice(-12)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Submitted</span>
                <span className="text-gray-800">{new Date(caseData?.created_at ?? '').toLocaleString()}</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── RIGHT: AI Output + Review Form ─────────────────── */}
        <div className="lg:col-span-8 space-y-5 page-enter" style={{ animationDelay: '100ms' }}>

          {/* AI Output Card */}
          {r && (
            <div className="bg-white rounded-2xl border border-gray-200 shadow-card overflow-hidden">
              {/* Header */}
              <div className={`px-6 py-5 ${ub.bg} border-b ${ub.border}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-1">AI Prediction</p>
                    <h2 className="text-3xl font-black text-gray-900 flex items-center gap-3">
                      {activeClass}
                      <span className="text-lg font-medium text-gray-500">
                        {ISIC_LABELS[activeClass ?? ''] ?? activeClass}
                      </span>
                    </h2>
                  </div>
                  <span className={`px-3 py-1.5 rounded-full text-xs font-bold border ${ub.bg} ${ub.text} ${ub.border}`}>
                    {urgency} URGENCY
                  </span>
                </div>
              </div>

              {/* Body */}
              <div className="p-6 grid sm:grid-cols-2 gap-6">
                <div className="space-y-5">
                  {/* Confidence */}
                  <div>
                    <div className="flex justify-between text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                      <span>Model Confidence</span>
                      <span className="text-gray-900">{(r.confidence * 100).toFixed(1)}%</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full">
                      <div
                        className="h-full rounded-full bar-fill bg-brand-600"
                        style={{ width: `${r.confidence * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Probabilities */}
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Top Probabilities</p>
                    <div className="space-y-1.5">
                      {Object.entries(r.all_probabilities)
                        .sort(([, a], [, b]) => b - a)
                        .slice(0, 4)
                        .map(([cls, prob]) => (
                          <div key={cls} className="flex items-center gap-3 text-xs">
                            <span className={`w-10 font-bold font-mono ${cls === r.predicted_class ? 'text-brand-600' : 'text-gray-400'}`}>
                              {cls}
                            </span>
                            <div className="flex-1 h-1.5 bg-gray-100 rounded-full">
                              <div
                                className={`h-full rounded-full ${cls === r.predicted_class ? 'bg-brand-600' : 'bg-gray-300'}`}
                                style={{ width: `${prob * 100}%` }}
                              />
                            </div>
                            <span className="w-8 text-right font-mono text-gray-400">{(prob * 100).toFixed(0)}%</span>
                          </div>
                        ))}
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  {/* Triage Factors */}
                  {r.urgency_reasons.length > 0 && (
                    <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">Triage Factors</p>
                      <ul className="space-y-1.5">
                        {r.urgency_reasons.map((reason, i) => (
                          <li key={i} className="flex items-start gap-2 text-[11px] text-gray-600 leading-snug">
                            <span className="text-brand-500 flex-shrink-0">⚡</span>
                            {reason}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Agent Synthesis */}
                  {r.agent_result && (
                    <div className="bg-brand-50 border border-brand-100 rounded-xl p-4">
                      <p className="text-[10px] font-bold text-brand-600 uppercase tracking-wider mb-2">
                        Agent Synthesis — {r.agent_status}
                      </p>
                      <p className="text-[11px] text-gray-600 leading-relaxed">
                        {String(
                          (r.agent_result as Record<string, unknown>).explanation
                          ?? (r.agent_result as Record<string, unknown>).referral_message
                          ?? (r.agent_result as Record<string, unknown>).followup_questions
                          ?? 'No explanation available.'
                        )}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ── Doctor Review Form ─────────────────────────────── */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-card p-6 sm:p-8">
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-100">
              <div>
                <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                  {reviewed
                    ? <span className="text-emerald-500">✓</span>
                    : <span className="text-brand-500">✍</span>}
                  {reviewed ? 'Clinical Review Logged' : 'Submit Clinical Review'}
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  {reviewed
                    ? `Reviewed by Dr. ${reviewed.doctor_name} on ${new Date(reviewed.reviewed_at).toLocaleString()}`
                    : 'Your decision will be recorded for patient reporting.'}
                </p>
              </div>
              {reviewed && (
                <span className="px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-bold border border-emerald-200">
                  Reviewed
                </span>
              )}
            </div>

            <form onSubmit={handleReviewSubmit} className="space-y-5">

              {/* Decision */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                  Diagnostic Decision
                </label>
                <div className="grid sm:grid-cols-2 gap-3">
                  {(['accepted', 'overridden'] as const).map(d => (
                    <label key={d} className={`flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition-all ${
                      decision === d
                        ? d === 'accepted'
                          ? 'bg-emerald-50 border-emerald-300'
                          : 'bg-amber-50 border-amber-300'
                        : 'bg-gray-50 border-gray-200 hover:bg-gray-100 hover:border-gray-300'
                    }`}>
                      <input
                        type="radio"
                        name="decision"
                        value={d}
                        checked={decision === d}
                        onChange={() => setDecision(d)}
                        className="hidden"
                      />
                      <div className={`mt-0.5 w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                        decision === d
                          ? (d === 'accepted' ? 'border-emerald-500 bg-emerald-500' : 'border-amber-500 bg-amber-500')
                          : 'border-gray-300 bg-white'
                      }`}>
                        {decision === d && <span className="text-white text-[10px] font-bold">✓</span>}
                      </div>
                      <div>
                        <div className={`text-sm font-bold mb-0.5 ${
                          decision === d
                            ? (d === 'accepted' ? 'text-emerald-700' : 'text-amber-700')
                            : 'text-gray-700'
                        }`}>
                          {d === 'accepted' ? 'Accept AI Prediction' : 'Override Prediction'}
                        </div>
                        <div className="text-xs text-gray-400">
                          {d === 'accepted' ? 'Confirm AI diagnosis is correct' : 'Provide a corrected diagnosis'}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Override class select */}
              {decision === 'overridden' && (
                <div className="scale-in">
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Corrected Diagnosis
                  </label>
                  <select
                    value={overrideClass}
                    onChange={e => setOverrideClass(e.target.value)}
                    className="input-field cursor-pointer appearance-none"
                  >
                    {ISIC_CLASSES.map(cls => (
                      <option key={cls} value={cls}>
                        {cls} — {ISIC_LABELS[cls]}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Clinical Notes */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Clinical Notes
                </label>
                <textarea
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  rows={4}
                  placeholder="Record observations, biopsy recommendations, or follow-up instructions (these will appear on the patient report)..."
                  className="input-field resize-y min-h-[100px]"
                />
              </div>

              <div className="pt-4 border-t border-gray-100 flex justify-end">
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-primary px-8 py-3 rounded-xl flex items-center justify-center gap-2 w-full sm:w-auto text-sm"
                >
                  {submitting ? (
                    <>
                      <span className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                        <polyline points="17 21 17 13 7 13 7 21"/>
                        <polyline points="7 3 7 8 15 8"/>
                      </svg>
                      {reviewed ? 'Update Review' : 'Save Review'}
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
