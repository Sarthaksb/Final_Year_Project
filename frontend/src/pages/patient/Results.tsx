import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { getCase, DiagnosisResult } from '../../api/diagnosis'
import UrgencyBadge from '../../components/UrgencyBadge'
import { useToast } from '../../components/Toast'

const ISIC_LABELS: Record<string, string> = {
  MEL: 'Melanoma', NV: 'Melanocytic Nevus', BCC: 'Basal Cell Carcinoma',
  AK: 'Actinic Keratosis', BKL: 'Benign Keratosis-like Lesion',
  DF: 'Dermatofibroma', VASC: 'Vascular Lesion', SCC: 'Squamous Cell Carcinoma',
}

const URGENCY_STYLES: Record<string, { bg: string, text: string, border: string, light: string }> = {
  HIGH:   { bg: 'bg-red-50',    text: 'text-red-700',    border: 'border-red-200', light: 'bg-red-100' },
  MEDIUM: { bg: 'bg-amber-50',  text: 'text-amber-700',  border: 'border-amber-200', light: 'bg-amber-100' },
  LOW:    { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', light: 'bg-emerald-100' },
}

interface ExtResult extends DiagnosisResult { _imageFilename?: string }

export default function Results() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const toast = useToast()

  const [result, setResult] = useState<ExtResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [showAllProbs, setShowAllProbs] = useState(false)
  const [activeTab, setActiveTab] = useState<'overview' | 'explanation' | 'heatmap'>('overview')

  useEffect(() => {
    if (caseId === 'latest') {
      const raw = sessionStorage.getItem('last_result')
      if (raw) {
        try { setResult(JSON.parse(raw) as ExtResult); setLoading(false); return } catch { /* ignore */ }
      }
      toast.error('No recent result found.')
      setLoading(false)
      return
    }
    getCase(caseId!)
      .then(c => {
        if (!c.result) { toast.warning('Case pending AI diagnosis.'); return }
        setResult({ ...c.result, _imageFilename: c.image_filename })
      })
      .catch(() => toast.error('Could not load case.'))
      .finally(() => setLoading(false))
  }, [caseId, toast])

  const copyLink = () => {
    navigator.clipboard.writeText(window.location.href)
    toast.success('Link copied to clipboard')
  }

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-64px)] flex items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-full border-2 border-brand-200 border-t-brand-600 animate-spin" />
          <p className="text-gray-500 text-sm font-medium">Retrieving clinical results...</p>
        </div>
      </div>
    )
  }

  if (!result) {
    return (
      <div className="min-h-[calc(100vh-64px)] flex items-center justify-center px-4 bg-gray-50">
        <div className="text-center max-w-sm bg-white rounded-2xl p-8 scale-in border border-gray-200 shadow-card">
          <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-4 border border-red-100">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-red-400">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          </div>
          <h2 className="text-lg font-bold text-gray-900 mb-2">Result Unavailable</h2>
          <p className="text-gray-500 text-sm mb-6">The requested case could not be found or has no analysis attached.</p>
          <Link to="/upload" className="btn-primary inline-flex px-6 py-2.5 text-sm rounded-xl">Return to Upload</Link>
        </div>
      </div>
    )
  }

  const urgStyle = URGENCY_STYLES[result.urgency] ?? URGENCY_STYLES.LOW
  const agentText = result.agent_result
    ? (result.agent_result['explanation'] as string)
      ?? (result.agent_result['referral_message'] as string)
      ?? (result.agent_result['followup_questions'] as string)
    : null

  return (
    <div className="min-h-[calc(100vh-64px)] py-8 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto flex flex-col lg:flex-row gap-6 bg-gray-50">

      {/* ── Left Column ─────────────────────────────────────── */}
      <div className="flex-1 space-y-5 page-enter">

        {/* Header Card */}
        <div className={`bg-white rounded-2xl border ${urgStyle.border} shadow-card overflow-hidden`}>
          <div className={`p-6 sm:p-8 ${urgStyle.bg}`}>
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-5">
              <div>
                <p className="text-brand-600 font-bold text-xs uppercase tracking-widest mb-2 flex items-center gap-1.5">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                    <polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
                  </svg>
                  Primary Prediction
                </p>
                <h1 className="text-3xl sm:text-4xl font-black text-gray-900 leading-tight">
                  {result.predicted_class}
                  <span className="block text-lg font-medium text-gray-600 mt-1">
                    {ISIC_LABELS[result.predicted_class] ?? result.predicted_class}
                  </span>
                </h1>
              </div>
              <UrgencyBadge urgency={result.urgency} size="lg" />
            </div>
            <p className="text-gray-700 leading-relaxed max-w-xl">{result.description}</p>
          </div>

          <div className="bg-white p-6 sm:p-8 border-t border-gray-100 space-y-5">
            {/* Confidence */}
            <div>
              <div className="flex justify-between items-end mb-2">
                <span className="text-sm font-semibold text-gray-600">AI Confidence Score</span>
                <span className="text-2xl font-black text-gray-900">{(result.confidence * 100).toFixed(1)}<span className="text-base text-gray-400">%</span></span>
              </div>
              <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bar-fill"
                  style={{
                    width: `${result.confidence * 100}%`,
                    background: result.is_high_risk ? '#EF4444' : '#2563EB',
                  }}
                />
              </div>
            </div>

            {/* High-risk alert */}
            {result.is_high_risk && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3 scale-in">
                <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-red-500">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                    <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                  </svg>
                </div>
                <div>
                  <p className="text-red-700 font-bold text-sm mb-1">High-Risk Classification Detected</p>
                  <p className="text-red-600/80 text-xs leading-relaxed">
                    This lesion exhibits characteristics of {ISIC_LABELS[result.predicted_class]}.
                    Clinical evaluation by a dermatologist is strongly recommended.
                  </p>
                </div>
              </div>
            )}

            {/* Urgency reasons */}
            {result.urgency_reasons.length > 0 && (
              <div className="pt-4 border-t border-gray-100">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Triage Factors</p>
                <div className="grid sm:grid-cols-2 gap-2">
                  {result.urgency_reasons.map((r, i) => (
                    <div key={i} className="flex items-start gap-2 bg-gray-50 rounded-lg p-2.5 border border-gray-100">
                      <span className="text-brand-500 flex-shrink-0 text-sm">⚡</span>
                      <span className="text-xs text-gray-600 leading-snug">{r}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="bg-white rounded-2xl overflow-hidden border border-gray-200 shadow-card">
          <div className="flex border-b border-gray-100 overflow-x-auto scrollbar-thin">
            {[
              { id: 'overview', label: 'All Probabilities', icon: '📊' },
              { id: 'explanation', label: 'AI Explanation', icon: '🤖' },
              { id: 'heatmap', label: 'Grad-CAM', icon: '👁️' },
            ].map(t => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id as any)}
                className={`flex items-center gap-2 px-6 py-4 text-sm font-semibold whitespace-nowrap transition-colors relative
                  ${activeTab === t.id ? 'text-brand-600' : 'text-gray-400 hover:text-gray-700 hover:bg-gray-50'}`}
              >
                <span>{t.icon}</span> {t.label}
                {activeTab === t.id && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-600" />
                )}
              </button>
            ))}
          </div>

          <div className="p-6">
            {/* Probabilities */}
            {activeTab === 'overview' && (
              <div className="space-y-4 scale-in">
                {Object.entries(result.all_probabilities)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, showAllProbs ? 8 : 4)
                  .map(([cls, prob], idx) => {
                    const isTop = idx === 0
                    return (
                      <div key={cls} className="flex items-center gap-4 group">
                        <div className="w-12 text-right">
                          <span className={`text-xs font-bold font-mono ${isTop ? 'text-gray-900' : 'text-gray-400'}`}>{cls}</span>
                        </div>
                        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-1000 ease-out
                              ${isTop ? 'bg-brand-600' : 'bg-gray-300 group-hover:bg-gray-400'}`}
                            style={{ width: `${prob * 100}%` }}
                          />
                        </div>
                        <div className="w-12 text-right">
                          <span className={`text-xs font-mono ${isTop ? 'text-gray-900 font-bold' : 'text-gray-400'}`}>
                            {(prob * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    )
                  })}
                <button
                  onClick={() => setShowAllProbs(s => !s)}
                  className="w-full mt-2 py-2 text-xs font-semibold text-brand-600 hover:text-brand-700 bg-brand-50 hover:bg-brand-100 rounded-lg transition-colors border border-brand-100"
                >
                  {showAllProbs ? 'Show Top 4 Only' : 'View All 8 Classes'}
                </button>
              </div>
            )}

            {/* Explanation */}
            {activeTab === 'explanation' && (
              <div className="space-y-5 scale-in">
                {agentText ? (
                  <div className="space-y-2">
                    <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-brand-600 animate-pulse" />
                      Agent Synthesis
                    </h3>
                    <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm text-gray-700 leading-relaxed">
                      {agentText}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 italic">No agent synthesis available for this case.</p>
                )}

                {result.rag_explanation && (
                  <div className="space-y-2">
                    <h3 className="text-sm font-bold text-brand-600 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-brand-400 animate-pulse" />
                      Medical Literature Context (RAG)
                    </h3>
                    <div className="bg-brand-50 border border-brand-100 rounded-xl p-4">
                      <p className="text-sm text-gray-700 leading-relaxed mb-3">{result.rag_explanation}</p>
                      {result.rag_source && (
                        <div className="flex items-center gap-2 text-xs text-gray-400 bg-white/80 px-3 py-1.5 rounded-lg border border-gray-100 inline-flex">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                          </svg>
                          <span className="font-mono">{result.rag_source}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Heatmap */}
            {activeTab === 'heatmap' && (
              <div className="scale-in">
                {result.gradcam_path ? (
                  <div className="bg-gray-50 border border-gray-200 rounded-xl overflow-hidden relative group">
                    <img
                      src={`/uploads/${result.gradcam_path.split('/').pop()}`}
                      alt="Grad-CAM heatmap"
                      className="w-full h-auto max-h-80 object-contain"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-4">
                      <p className="text-xs text-white">Red/yellow areas indicate regions that strongly influenced the model's prediction.</p>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-center border border-dashed border-gray-200 rounded-xl bg-gray-50">
                    <span className="text-3xl mb-2 opacity-40">👁️</span>
                    <p className="text-sm text-gray-400">Grad-CAM visualization not generated for this case.</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Right Column ────────────────────────────────────── */}
      <div className="w-full lg:w-80 space-y-4 page-enter" style={{ animationDelay: '100ms' }}>

        {/* Next Steps */}
        <div className="stat-card">
          <h3 className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-brand-500">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
            Next Steps
          </h3>
          <p className="text-xs text-gray-500 leading-relaxed mb-4">
            This AI screening has been logged in your history. If you are a patient,
            please share this result with your dermatologist.
          </p>
          <div className="space-y-2">
            <button onClick={copyLink} className="w-full py-2.5 btn-secondary rounded-lg text-xs font-semibold flex items-center justify-center gap-2">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
              Copy Report Link
            </button>
            <Link to="/upload" className="w-full flex py-2.5 btn-primary rounded-lg text-xs font-semibold items-center justify-center gap-2">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              New Scan
            </Link>
          </div>
        </div>

        {/* Disclaimer */}
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <div className="flex gap-2 mb-1">
            <span className="text-amber-500 text-sm">⚕️</span>
            <span className="text-xs font-bold text-amber-700 uppercase tracking-wider">Medical Disclaimer</span>
          </div>
          <p className="text-[11px] text-amber-700/70 leading-relaxed">
            DermaAI is a clinical decision support tool, not a diagnostic device.
            Results must be verified by a certified medical professional.
          </p>
        </div>

        {/* Technical details */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-card">
          <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">Technical Details</h4>
          <div className="space-y-1.5">
            {[
              { l: 'Model', v: 'EfficientNet-B0' },
              { l: 'Triage Agent', v: 'Gemini 1.5 Flash' },
              { l: 'Case ID', v: caseId === 'latest' ? 'Pending' : (caseId?.slice(-8) ?? '—') },
            ].map(row => (
              <div key={row.l} className="flex justify-between text-[11px]">
                <span className="text-gray-400">{row.l}</span>
                <span className="text-gray-800 font-mono truncate w-28 text-right">{row.v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
