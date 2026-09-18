import { useEffect, useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { getDoctorCases, getDoctorStats, DoctorCaseOut, DashboardStats } from '../../api/doctor'
import UrgencyBadge from '../../components/UrgencyBadge'
import { useToast } from '../../components/Toast'

function formatDate(iso: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
  }).format(new Date(iso))
}

export default function Dashboard() {
  const [cases, setCases] = useState<DoctorCaseOut[]>([])
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'ALL' | 'PENDING' | 'REVIEWED'>('ALL')
  const toast = useToast()

  useEffect(() => {
    Promise.all([getDoctorCases(), getDoctorStats()])
      .then(([casesData, statsData]) => { setCases(casesData); setStats(statsData) })
      .catch(() => toast.error('Failed to load clinic cases.'))
      .finally(() => setLoading(false))
  }, [toast])

  const filtered = useMemo(() => {
    if (filter === 'ALL') return cases
    if (filter === 'PENDING') return cases.filter(c => !c.doctor_review)
    return cases.filter(c => !!c.doctor_review)
  }, [cases, filter])

  return (
    <div className="min-h-[calc(100vh-64px)] py-8 px-4 sm:px-6 bg-gray-50">
      <div className="max-w-6xl mx-auto page-enter">

        {/* ── Header ─────────────────────────────────────────── */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight mb-1">Clinical Dashboard</h1>
          <p className="text-gray-500 text-sm">Review AI screening results, override predictions, and generate reports.</p>
        </div>

        {/* ── Stats Row ──────────────────────────────────────── */}
        {!loading && cases.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-7 scale-in">
            <div className="stat-card">
              <div className="text-2xl font-black text-gray-900">{stats?.total ?? '—'}</div>
              <div className="text-xs text-gray-400 uppercase tracking-wider mt-1">Total Cases</div>
            </div>
            <div className="stat-card border-brand-200 bg-brand-50/60">
              <div className="text-2xl font-black text-brand-600">{stats?.pending_review ?? '—'}</div>
              <div className="text-xs text-brand-500 uppercase tracking-wider mt-1">Pending Review</div>
            </div>
            <div className="stat-card border-red-200 bg-red-50/60">
              <div className="flex items-center gap-2">
                <span className="text-2xl font-black text-red-500">{stats?.high ?? '—'}</span>
                {(stats?.high ?? 0) > 0 && <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />}
              </div>
              <div className="text-xs text-red-400 uppercase tracking-wider mt-1">HIGH Urgency</div>
            </div>
            <div className="stat-card border-emerald-200 bg-emerald-50/60">
              <div className="text-2xl font-black text-emerald-600">{stats?.reviewed ?? '—'}</div>
              <div className="text-xs text-emerald-500 uppercase tracking-wider mt-1">Reviewed</div>
            </div>
          </div>
        )}

        {/* ── Filter Tabs ─────────────────────────────────────── */}
        {!loading && cases.length > 0 && (
          <div className="flex bg-white border border-gray-200 rounded-xl p-1 mb-5 w-full max-w-sm scale-in shadow-card">
            {(['ALL', 'PENDING', 'REVIEWED'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
                  filter === f
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'text-gray-400 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        )}

        {/* ── Cases Table ─────────────────────────────────────── */}
        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="h-16 bg-white border border-gray-100 rounded-xl shimmer" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20 bg-white rounded-3xl border border-dashed border-gray-200 shadow-card scale-in">
            <div className="w-16 h-16 rounded-full bg-brand-50 flex items-center justify-center mx-auto mb-4 border border-brand-100">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-brand-400">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
              </svg>
            </div>
            <h2 className="text-lg font-bold text-gray-900 mb-2">No Cases Found</h2>
            <p className="text-gray-400 text-sm">
              {filter === 'ALL' ? 'There are no patient scans in the system yet.' : `No cases matching the ${filter} filter.`}
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-2xl overflow-hidden border border-gray-200 shadow-card scale-in">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">Patient ID</th>
                    <th className="px-6 py-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">Date</th>
                    <th className="px-6 py-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">AI Pred</th>
                    <th className="px-6 py-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">Conf</th>
                    <th className="px-6 py-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">Urgency</th>
                    <th className="px-6 py-4 font-semibold text-gray-500 text-xs uppercase tracking-wider">Review</th>
                    <th className="px-6 py-4 font-semibold text-gray-500 text-xs uppercase tracking-wider text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filtered.map(c => {
                    const r = c.result
                    const rev = c.doctor_review
                    return (
                      <tr key={c.id} className="data-row group hover:bg-gray-50">
                        <td className="px-6 py-4 font-mono text-xs text-gray-600 font-semibold">
                          #{c.user_id.slice(-6).toUpperCase()}
                        </td>
                        <td className="px-6 py-4 text-xs text-gray-500">{formatDate(c.created_at)}</td>
                        <td className="px-6 py-4">
                          {r ? (
                            <span className={`font-bold text-sm ${r.is_high_risk ? 'text-red-600' : 'text-gray-900'}`}>
                              {r.predicted_class}
                            </span>
                          ) : (
                            <span className="text-gray-300 italic text-xs">Pending</span>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          {r ? (
                            <span className="font-mono text-xs text-gray-600">
                              {(r.confidence * 100).toFixed(1)}%
                            </span>
                          ) : '-'}
                        </td>
                        <td className="px-6 py-4">
                          {r ? <UrgencyBadge urgency={r.urgency} size="sm" animate={!rev} /> : '-'}
                        </td>
                        <td className="px-6 py-4">
                          {rev ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200">
                              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                                <polyline points="20 6 9 17 4 12"/>
                              </svg>
                              REVIEWED
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 text-[10px] font-bold border border-amber-200">
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                              PENDING
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <Link
                            to={`/doctor/cases/${c.id}`}
                            className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700 transition-colors"
                          >
                            {rev ? 'View Details' : 'Review Case'}
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M5 12h14M12 5l7 7-7 7"/>
                            </svg>
                          </Link>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
