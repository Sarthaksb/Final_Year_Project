import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getLesions, createLesion, Lesion } from '../../api/diagnosis'
import { useToast } from '../../components/Toast'

export default function Lesions() {
  const [lesions, setLesions] = useState<Lesion[]>([])
  const [loading, setLoading] = useState(true)
  const [showNew, setShowNew] = useState(false)
  const [site, setSite] = useState('')
  const [label, setLabel] = useState('')
  const toast = useToast()

  const loadLesions = () => {
    setLoading(true)
    getLesions()
      .then(setLesions)
      .catch(() => toast.error('Failed to load tracked lesions.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadLesions()
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!site || !label) return toast.error('Both fields are required')
    try {
      const created = await createLesion(site, label)
      setLesions(prev => [...prev, created])
      setShowNew(false)
      setSite('')
      setLabel('')
      toast.success('Tracked lesion created.')
    } catch {
      toast.error('Failed to create lesion.')
    }
  }

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-64px)] flex items-center justify-center bg-gray-50">
        <div className="w-12 h-12 rounded-full border-2 border-brand-200 border-t-brand-600 animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-[calc(100vh-64px)] py-12 px-4 sm:px-6 bg-gray-50">
      <div className="max-w-4xl mx-auto page-enter">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Tracked Lesions</h1>
            <p className="text-sm text-gray-500 mt-1">Monitor changes in specific skin areas over time.</p>
          </div>
          <button
            onClick={() => setShowNew(!showNew)}
            className="btn-primary px-4 py-2 rounded-xl text-sm"
          >
            {showNew ? 'Cancel' : '+ New Lesion'}
          </button>
        </div>

        {showNew && (
          <form onSubmit={handleCreate} className="bg-white p-5 rounded-2xl shadow-card border border-gray-200 mb-6 scale-in flex gap-4 items-end">
            <div className="flex-1">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Body Site (e.g., Left Arm)</label>
              <input value={site} onChange={e => setSite(e.target.value)} className="input-field" placeholder="Left Arm" />
            </div>
            <div className="flex-1">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Description Label</label>
              <input value={label} onChange={e => setLabel(e.target.value)} className="input-field" placeholder="Dark mole near elbow" />
            </div>
            <button type="submit" className="btn-secondary px-6 py-3 rounded-xl text-sm font-bold h-[46px]">
              Save
            </button>
          </form>
        )}

        <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-5">
          {lesions.map(lesion => (
            <Link key={lesion._id} to={`/lesions/${lesion._id}/timeline`} className="group block bg-white p-5 rounded-2xl shadow-sm border border-gray-200 hover:border-brand-300 hover:shadow-card transition-all">
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-full bg-brand-50 flex items-center justify-center text-brand-600">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                </div>
              </div>
              <h3 className="font-bold text-gray-900 group-hover:text-brand-700 transition-colors">{lesion.label}</h3>
              <p className="text-sm text-gray-500 mb-4">{lesion.body_site}</p>
              <div className="text-xs text-brand-600 font-semibold flex items-center justify-between">
                View Timeline →
              </div>
            </Link>
          ))}
          
          {lesions.length === 0 && !showNew && (
            <div className="col-span-full py-12 text-center text-gray-400">
              No tracked lesions yet. Create one to start monitoring over time.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
