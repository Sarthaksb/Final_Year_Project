import { useEffect, useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { getCases, deleteCase, CaseOut } from '../../api/diagnosis'
import UrgencyBadge from '../../components/UrgencyBadge'
import { useToast } from '../../components/Toast'

const ISIC_LABELS: Record<string, string> = {
  MEL: 'Melanoma', NV: 'Melanocytic Nevus', BCC: 'Basal Cell Carcinoma',
  AK: 'Actinic Keratosis', BKL: 'Benign Keratosis', DF: 'Dermatofibroma',
  VASC: 'Vascular Lesion', SCC: 'Squamous Cell Carcinoma',
}

function formatDate(iso: string) {
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(iso))
}
function formatTime(iso: string) {
  return new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }).format(new Date(iso))
}

export default function Home() {
  const [cases, setCases] = useState<CaseOut[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [urgencyFilter, setUrgencyFilter] = useState<string>('ALL')
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const toast = useToast()

  useEffect(() => {
    getCases()
      .then(setCases)
      .catch(() => toast.error('Failed to load history. Please try again later.'))
      .finally(() => setLoading(false))
  }, [toast])

  const handleDelete = async (e: React.MouseEvent, caseId: string) => {
    e.preventDefault()
    e.stopPropagation()
    if (!window.confirm('Permanently delete this scan and its image? This cannot be undone.')) return
    setDeletingId(caseId)
    try {
      await deleteCase(caseId)
      setCases(prev => prev.filter(c => c.id !== caseId))
      toast.success('Scan deleted successfully.')
    } catch {
      toast.error('Failed to delete scan. Please try again.')
    } finally {
      setDeletingId(null)
    }
  }

  const filteredCases = useMemo(() => {
    return cases.filter(c => {
      const u = c.result?.urgency || 'UNKNOWN'
      const matchesUrgency = urgencyFilter === 'ALL' || u === urgencyFilter
      const searchLower = searchQuery.toLowerCase()
      const predClass = c.result?.predicted_class?.toLowerCase() || ''
      const predName = ISIC_LABELS[c.result?.predicted_class || '']?.toLowerCase() || ''
      const matchesSearch =
        searchQuery === '' ||
        c.id.toLowerCase().includes(searchLower) ||
        predClass.includes(searchLower) ||
        predName.includes(searchLower)
      return matchesUrgency && matchesSearch
    })
  }, [cases, urgencyFilter, searchQuery])

  const stats = useMemo(() => ({
    total: cases.length,
    high: cases.filter(c => c.result?.urgency === 'HIGH').length,
    highRiskClasses: cases.filter(c => c.result?.is_high_risk).length,
  }), [cases])

  return (
    <div className="min-h-[calc(100vh-64px)] py-8 px-4 sm:px-6 bg-gray-50">
      <div className="max-w-5xl mx-auto page-enter">

        {/* ── Header ───────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight mb-1">My Scan History</h1>
            <p className="text-gray-500 text-sm">View and manage all your past AI dermatology screenings.</p>
          </div>
          <Link
            to="/upload"
            className="btn-primary px-6 py-2.5 text-sm flex items-center justify-center gap-2 flex-shrink-0 rounded-xl"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            New Scan
          </Link>
        </div>

        {/* ── Stats Bar ───────────────────────────────────────── */}
        {!loading && cases.length > 0 && (
          <div className="grid grid-cols-3 gap-3 mb-6 scale-in">
            <div className="stat-card">
              <div className="text-2xl font-black text-gray-900">{stats.total}</div>
              <div className="text-xs text-gray-400 font-medium mt-0.5">Total Scans</div>
            </div>
            <div className="stat-card border-red-100 bg-red-50/50">
              <div className="text-2xl font-black text-red-500">{stats.high}</div>
              <div className="text-xs text-red-400 font-medium mt-0.5">HIGH Urgency</div>
            </div>
            <div className="stat-card border-amber-100 bg-amber-50/50">
              <div className="text-2xl font-black text-amber-500">{stats.highRiskClasses}</div>
              <div className="text-xs text-amber-400 font-medium mt-0.5">High Risk Classes</div>
            </div>
          </div>
        )}

        {/* ── Filters & Search ─────────────────────────────────── */}
        {!loading && cases.length > 0 && (
          <div className="flex flex-col sm:flex-row items-center gap-3 mb-5 scale-in">
            <div className="relative w-full sm:flex-1">
              <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
              </div>
              <input
                type="text"
                placeholder="Search by case ID or class..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="input-field pl-10"
              />
            </div>
            <div className="flex w-full sm:w-auto bg-white border border-gray-200 rounded-xl p-1 overflow-x-auto scrollbar-thin shadow-card">
              {(['ALL', 'HIGH', 'MEDIUM', 'LOW'] as const).map(u => (
                <button
                  key={u}
                  onClick={() => setUrgencyFilter(u)}
                  className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-colors whitespace-nowrap flex-1 sm:flex-none
                    ${urgencyFilter === u
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'text-gray-500 hover:text-gray-800 hover:bg-gray-50'}`}
                >
                  {u}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Content ─────────────────────────────────────────── */}
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-24 bg-white border border-gray-100 rounded-2xl shimmer" />
            ))}
          </div>
        ) : cases.length === 0 ? (
          <div className="text-center py-20 bg-white rounded-3xl border border-gray-200 border-dashed shadow-card scale-in">
            <div className="w-20 h-20 rounded-full bg-brand-50 border border-brand-100 flex items-center justify-center mx-auto mb-5">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-brand-400">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
            </div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">No Scans Yet</h2>
            <p className="text-gray-500 text-sm max-w-sm mx-auto mb-8 leading-relaxed">
              Upload your first skin lesion image to receive an AI-assisted triage and analysis report.
            </p>
            <Link to="/upload" className="btn-primary inline-flex px-8 py-3 text-sm rounded-xl">
              Start First Scan →
            </Link>
          </div>
        ) : filteredCases.length === 0 ? (
          <div className="text-center py-16 text-gray-400 scale-in">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto mb-4 opacity-40">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <p className="text-base font-medium text-gray-700 mb-1">No matches found</p>
            <p className="text-sm">Try adjusting your search or filters.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filteredCases.map(c => {
              const r = c.result
              return (
                <Link
                  key={c.id}
                  to={`/results/${c.id}`}
                  className="data-row bg-white rounded-2xl p-4 flex gap-4 items-start border border-gray-200 shadow-card relative group overflow-hidden hover:shadow-card-md hover:-translate-y-0.5 transition-all"
                >
                  {/* Thumbnail */}
                  <div className="w-18 h-18 w-[72px] h-[72px] rounded-xl bg-gray-100 border border-gray-200 flex-shrink-0 flex items-center justify-center overflow-hidden">
                    <img
                      src={`/uploads/${c.image_filename}`}
                      alt="Lesion"
                      className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                      onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                    />
                    {!c.image_filename && (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-gray-300">
                        <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>
                      </svg>
                    )}
                  </div>

                  {/* Details */}
                  <div className="flex-1 min-w-0 py-0.5">
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <div className="min-w-0">
                        <h3 className="font-bold text-gray-900 text-sm truncate">
                          {r?.predicted_class ?? 'Pending Analysis'}
                        </h3>
                        <p className="text-xs text-gray-400 truncate">
                          {r ? ISIC_LABELS[r.predicted_class] : 'Upload received'}
                        </p>
                      </div>
                      <div className="flex-shrink-0">
                        {r ? <UrgencyBadge urgency={r.urgency} size="sm" animate={false} /> : (
                          <span className="px-2 py-0.5 rounded-full bg-gray-100 border border-gray-200 text-gray-500 text-[10px] font-bold">
                            PENDING
                          </span>
                        )}
                      </div>
                    </div>

                    {r && (
                      <div className="mt-2 flex items-center gap-3">
                        <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-700
                              ${r.is_high_risk ? 'bg-red-400' : 'bg-brand-500'}`}
                            style={{ width: `${r.confidence * 100}%` }}
                          />
                        </div>
                        <span className="text-[10px] font-mono text-gray-400 w-8">
                          {(r.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    )}

                    <div className="flex items-center justify-between mt-2.5">
                      <p className="text-[10px] text-gray-400 font-medium">
                        {formatDate(c.created_at)} · {formatTime(c.created_at)}
                      </p>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={e => handleDelete(e, c.id)}
                          disabled={deletingId === c.id}
                          title="Delete this scan"
                          className="p-1 rounded-md text-gray-300 hover:text-red-400 hover:bg-red-50
                                     transition-colors opacity-0 group-hover:opacity-100 disabled:opacity-50"
                        >
                          {deletingId === c.id ? (
                            <span className="w-3 h-3 rounded-full border border-red-400 border-t-transparent animate-spin block" />
                          ) : (
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                              <path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                            </svg>
                          )}
                        </button>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-brand-400 opacity-0 group-hover:opacity-100 transform -translate-x-2 group-hover:translate-x-0 transition-all">
                          <path d="M5 12h14M12 5l7 7-7 7"/>
                        </svg>
                      </div>
                    </div>
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
