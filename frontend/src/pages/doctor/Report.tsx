import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { downloadReport } from '../../api/doctor'

export default function Report() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const [status, setStatus] = useState<'loading' | 'done' | 'error'>('loading')

  useEffect(() => {
    if (!caseId) { setStatus('error'); return }
    downloadReport(caseId)
      .then(() => setStatus('done'))
      .catch(() => setStatus('error'))
  }, [caseId])

  return (
    <div className="min-h-[calc(100vh-64px)] flex items-center justify-center bg-gray-50 px-6">
      <div className="text-center max-w-md w-full bg-white rounded-3xl p-10 scale-in border border-gray-200 shadow-card-lg">

        {status === 'loading' && (
          <div className="flex flex-col items-center">
            <div className="w-16 h-16 rounded-full border-[3px] border-brand-100 border-t-brand-600 animate-spin mb-6" />
            <h2 className="text-xl font-bold text-gray-900 mb-2">Generating PDF Report</h2>
            <p className="text-gray-500 text-sm">Please wait while the clinical report is compiled and downloaded...</p>
          </div>
        )}

        {status === 'done' && (
          <div className="flex flex-col items-center scale-in">
            <div className="w-16 h-16 bg-emerald-50 border border-emerald-200 rounded-full flex items-center justify-center mb-6 shadow-sm">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-500">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            </div>
            <h2 className="text-xl font-bold text-emerald-700 mb-2">Report Downloaded</h2>
            <p className="text-gray-500 text-sm mb-8 leading-relaxed">
              The PDF report for case{' '}
              <span className="font-mono text-brand-600">{caseId?.slice(0, 12)}</span>{' '}
              has been securely saved to your local device.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 w-full justify-center">
              <button
                onClick={() => navigate(`/doctor/cases/${caseId}`)}
                className="btn-secondary px-6 py-2.5 rounded-xl text-sm font-semibold w-full sm:w-auto"
              >
                Back to Case
              </button>
              <button
                onClick={() => navigate('/doctor')}
                className="btn-primary px-6 py-2.5 rounded-xl text-sm font-semibold w-full sm:w-auto"
              >
                Dashboard
              </button>
            </div>
          </div>
        )}

        {status === 'error' && (
          <div className="flex flex-col items-center scale-in">
            <div className="w-16 h-16 bg-red-50 border border-red-200 rounded-full flex items-center justify-center mb-6 shadow-sm">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-red-400">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </div>
            <h2 className="text-xl font-bold text-red-600 mb-2">Generation Failed</h2>
            <p className="text-gray-500 text-sm mb-8 leading-relaxed">
              An error occurred while compiling the PDF document. Please ensure the backend rendering service is available.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 w-full justify-center">
              <button
                onClick={() => {
                  setStatus('loading')
                  if (caseId) downloadReport(caseId).then(() => setStatus('done')).catch(() => setStatus('error'))
                }}
                className="btn-primary px-6 py-2.5 rounded-xl text-sm font-semibold w-full sm:w-auto"
              >
                Retry Download
              </button>
              <button
                onClick={() => navigate('/doctor')}
                className="btn-secondary px-6 py-2.5 rounded-xl text-sm font-semibold w-full sm:w-auto"
              >
                Dashboard
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
