import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getLesionTimeline, TimelineItem, Lesion } from '../../api/diagnosis'
import { useToast } from '../../components/Toast'

export default function LesionTimeline() {
  const { lesionId } = useParams<{ lesionId: string }>()
  const [data, setData] = useState<{ lesion: Lesion; timeline: TimelineItem[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const toast = useToast()

  useEffect(() => {
    if (!lesionId) return
    getLesionTimeline(lesionId)
      .then(setData)
      .catch(() => toast.error('Failed to load timeline.'))
      .finally(() => setLoading(false))
  }, [lesionId, toast])

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-64px)] flex items-center justify-center bg-gray-50">
        <div className="w-12 h-12 rounded-full border-2 border-brand-200 border-t-brand-600 animate-spin" />
      </div>
    )
  }

  if (!data) return <div className="p-12 text-center">Not found.</div>

  const { lesion, timeline } = data

  return (
    <div className="min-h-[calc(100vh-64px)] py-12 px-4 sm:px-6 bg-gray-50">
      <div className="max-w-3xl mx-auto page-enter">
        <div className="mb-8">
          <Link to="/lesions" className="text-sm font-medium text-gray-500 hover:text-gray-900 mb-4 inline-flex items-center gap-1">
            ← Back to Lesions
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-2">{lesion.label}</h1>
          <p className="text-sm text-gray-500">{lesion.body_site} • Tracked since {new Date(lesion.created_at).toLocaleDateString()}</p>
        </div>

        {/* Chart Summary */}
        <div className="bg-white p-6 rounded-2xl shadow-card border border-gray-200 mb-8">
          <h3 className="font-bold text-gray-900 mb-4 text-sm uppercase tracking-wider">Malignancy Score Trend</h3>
          <div className="h-48 flex items-end gap-2">
            {timeline.map((item, i) => (
              <div key={i} className="flex-1 flex flex-col items-center justify-end group relative">
                {/* Tooltip */}
                <div className="absolute -top-10 opacity-0 group-hover:opacity-100 transition-opacity bg-gray-900 text-white text-xs px-2 py-1 rounded">
                  {(item.malignancy_score * 100).toFixed(1)}%
                </div>
                <div 
                  className={`w-full rounded-t-sm transition-all ${item.changed_flag ? 'bg-red-500' : 'bg-brand-500'}`} 
                  style={{ height: `${Math.max(item.malignancy_score * 100, 5)}%` }} 
                />
                <span className="text-[10px] text-gray-400 mt-2 rotate-45 origin-left truncate w-full block">
                  {new Date(item.created_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Timeline list */}
        <div className="space-y-6">
          {timeline.map((item, index) => (
            <div key={item.case_id} className="relative flex gap-6 bg-white p-5 rounded-2xl shadow-sm border border-gray-200">
              <div className="w-24 h-24 flex-shrink-0 bg-gray-100 rounded-xl overflow-hidden">
                <img src={`/uploads/${item.image_filename}`} alt="Lesion" className="w-full h-full object-cover" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">
                    Scan {index + 1}
                  </span>
                  <span className="text-xs text-gray-500">{new Date(item.created_at).toLocaleString()}</span>
                </div>
                <h4 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                  {item.predicted_class || 'Unknown'}
                  {item.changed_flag && (
                    <span className="px-2 py-0.5 rounded text-[10px] bg-red-100 text-red-700 font-bold">
                      SIGNIFICANT CHANGE ({(item.score_diff * 100).toFixed(1)}%)
                    </span>
                  )}
                </h4>
                <p className="text-sm text-gray-500 mt-1">
                  Urgency: <strong>{item.urgency}</strong> • Confidence: {((item.confidence || 0) * 100).toFixed(1)}%
                </p>
                <Link to={`/results/${item.case_id}`} className="text-brand-600 text-sm font-semibold hover:underline inline-block mt-3">
                  View Full Report →
                </Link>
              </div>
            </div>
          ))}
          {timeline.length === 0 && (
            <p className="text-center text-gray-400 py-8">No scans linked to this lesion yet.</p>
          )}
        </div>
      </div>
    </div>
  )
}
