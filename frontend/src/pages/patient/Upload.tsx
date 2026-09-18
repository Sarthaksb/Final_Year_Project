import { useState, useRef, useCallback, DragEvent, ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { analyzeImage, SymptomForm } from '../../api/diagnosis'
import { useToast } from '../../components/Toast'

const SYMPTOMS: { key: keyof SymptomForm; label: string; desc: string; risk: 'high' | 'medium' }[] = [
  { key: 'rapid_growth',      label: 'Rapid Growth',      desc: 'Lesion grew noticeably in the past few weeks',  risk: 'high' },
  { key: 'bleeding',          label: 'Bleeding',           desc: 'Bleeds spontaneously or on slight touch',       risk: 'high' },
  { key: 'irregular_border',  label: 'Irregular Border',   desc: 'Uneven, jagged, or poorly defined edges',      risk: 'high' },
  { key: 'itching',           label: 'Itching',            desc: 'Persistent itch, irritation, or tenderness',    risk: 'medium' },
  { key: 'pain',              label: 'Pain',               desc: 'Painful to touch or spontaneous throbbing',     risk: 'medium' },
]

const ACCEPT_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
const MAX_SIZE_MB = 10

export default function Upload() {
  const navigate = useNavigate()
  const toast = useToast()

  const [file, setFile]         = useState<File | null>(null)
  const [preview, setPreview]   = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [symptoms, setSymptoms] = useState<SymptomForm>({
    rapid_growth: false, bleeding: false, irregular_border: false,
    itching: false, pain: false,
  })
  const [loading, setLoading]   = useState(false)
  const [progress, setProgress] = useState(0)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const applyFile = useCallback((f: File) => {
    if (!ACCEPT_TYPES.includes(f.type)) {
      toast.error('Only JPEG, PNG, or WebP images are supported.')
      return
    }
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      toast.error(`Image must be smaller than ${MAX_SIZE_MB} MB.`)
      return
    }
    setFile(f)
    setPreview(URL.createObjectURL(f))
  }, [toast])

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) applyFile(dropped)
  }

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0]
    if (picked) applyFile(picked)
  }

  const toggleSymptom = (key: keyof SymptomForm) =>
    setSymptoms(s => ({ ...s, [key]: !s[key] }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) { toast.warning('Please select an image first.'); return }
    setLoading(true)
    setProgress(0)
    const tick = setInterval(() => setProgress(p => Math.min(p + (Math.random() * 5 + 2), 90)), 500)
    try {
      const result = await analyzeImage(file, symptoms)
      clearInterval(tick)
      setProgress(100)
      sessionStorage.setItem('last_result', JSON.stringify(result))
      setTimeout(() => navigate('/results/latest'), 400)
    } catch (err: unknown) {
      clearInterval(tick)
      setProgress(0)
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg ?? 'Analysis failed. Please try again.')
      setLoading(false)
    }
  }

  const clearFile = () => {
    setFile(null)
    setPreview(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const activeCount = Object.values(symptoms).filter(Boolean).length

  return (
    <div className="min-h-[calc(100vh-64px)] py-12 px-6 bg-gray-50">
      <div className="max-w-2xl mx-auto page-enter">

        {/* ── Header ─────────────────────────────────────────── */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-brand-200 bg-brand-50 mb-4">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-brand-600">
              <path d="M2 12h4l3-9 5 18 3-9h5"/>
            </svg>
            <span className="text-xs font-semibold text-brand-700">AI Analysis</span>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">New Diagnostic Scan</h1>
          <p className="text-gray-500 text-sm max-w-lg mx-auto leading-relaxed">
            Upload a clear, well-lit photo of the skin lesion. Provide accurate symptom
            information to improve the AI's triage accuracy.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">

          {/* ── Drop Zone ──────────────────────────────────────── */}
          <div className="card p-1">
            <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3 px-4 pt-4">
              Lesion Image
            </label>

            {preview ? (
              <div className="bg-gray-50 rounded-xl p-4 flex flex-col sm:flex-row items-center gap-6 mx-1 mb-1">
                <div className="w-full sm:w-44 h-44 rounded-xl overflow-hidden bg-gray-100 border border-gray-200 flex-shrink-0">
                  <img src={preview} alt="Selected lesion" className="w-full h-full object-contain" />
                </div>
                <div className="flex-1 w-full text-center sm:text-left">
                  <h3 className="text-sm font-semibold text-gray-900 truncate mb-1">{file?.name}</h3>
                  <p className="text-xs text-gray-400 mb-4">{(file!.size / 1024 / 1024).toFixed(2)} MB</p>
                  <div className="flex gap-2 justify-center sm:justify-start">
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="btn-secondary px-4 py-2 rounded-lg text-xs font-medium"
                    >
                      Change Image
                    </button>
                    <button
                      type="button"
                      onClick={clearFile}
                      className="px-4 py-2 hover:bg-red-50 hover:text-red-500 text-gray-400 rounded-lg text-xs font-medium transition-all"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div
                onDragOver={e => { e.preventDefault(); setDragging(true) }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`drop-zone rounded-xl p-12 text-center mx-1 mb-1 ${dragging ? 'drag-active' : ''}`}
              >
                <div className="w-14 h-14 rounded-xl bg-brand-50 border border-brand-100
                                flex items-center justify-center mx-auto mb-4">
                  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-brand-500">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                </div>
                <p className="text-gray-900 font-semibold mb-1">Drag & drop an image here</p>
                <p className="text-gray-500 text-sm mb-3">
                  or <span className="text-brand-600 font-medium">click to browse files</span>
                </p>
                <p className="text-xs text-gray-400 font-mono">JPEG, PNG, WebP · Max {MAX_SIZE_MB}MB</p>
              </div>
            )}

            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/jpg,image/png,image/webp"
              onChange={handleFileChange}
              className="hidden"
            />
          </div>

          {/* ── Symptom Checklist ───────────────────────────────── */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <label className="block text-sm font-bold text-gray-900">Clinical Symptoms</label>
                <p className="text-xs text-gray-500 mt-0.5">Select all that apply to improve triage accuracy</p>
              </div>
              {activeCount > 0 && (
                <span className="text-[11px] font-bold px-2.5 py-1 bg-brand-50 text-brand-700 rounded-full border border-brand-200 scale-in">
                  {activeCount} selected
                </span>
              )}
            </div>

            <div className="grid sm:grid-cols-2 gap-2.5">
              {SYMPTOMS.map(({ key, label, desc, risk }) => {
                const active = symptoms[key]
                const riskStyles = risk === 'high'
                  ? { active: 'bg-red-50 border-red-300', check: 'bg-red-500 border-red-500', label: 'text-red-700', dot: 'bg-red-400' }
                  : { active: 'bg-amber-50 border-amber-300', check: 'bg-amber-500 border-amber-500', label: 'text-amber-700', dot: 'bg-amber-400' }

                return (
                  <label
                    key={key}
                    htmlFor={`sym-${key}`}
                    className={`flex items-start gap-3 p-3.5 rounded-xl cursor-pointer transition-all border
                      ${active
                        ? `${riskStyles.active}`
                        : 'bg-gray-50 border-gray-200 hover:bg-gray-100 hover:border-gray-300'
                      }`}
                  >
                    <input
                      type="checkbox"
                      id={`sym-${key}`}
                      checked={active}
                      onChange={() => toggleSymptom(key)}
                      className="hidden"
                    />
                    <div className={`mt-0.5 w-5 h-5 rounded-[5px] border-2 flex items-center justify-center flex-shrink-0 transition-colors
                      ${active ? `${riskStyles.check}` : 'border-gray-300 bg-white'}`}>
                      {active && <span className="text-white text-[10px] font-bold">✓</span>}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        {active && <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${riskStyles.dot}`} />}
                        <span className={`text-sm font-semibold truncate ${active ? riskStyles.label : 'text-gray-800'}`}>
                          {label}
                        </span>
                      </div>
                      <div className="text-[11px] text-gray-400 leading-tight">{desc}</div>
                    </div>
                  </label>
                )
              })}
            </div>
          </div>

          {/* ── Action / Progress ──────────────────────────────── */}
          <div className="relative">
            {loading ? (
              <div className="card p-5 border-brand-200 bg-brand-50 scale-in">
                <div className="flex justify-between text-xs text-gray-700 mb-2.5 font-medium">
                  <span className="flex items-center gap-2">
                    <span className="w-3.5 h-3.5 rounded-full border-2 border-brand-600 border-t-transparent animate-spin" />
                    AI Agent is analyzing your scan...
                  </span>
                  <span className="font-mono font-bold text-brand-700">{Math.round(progress)}%</span>
                </div>
                <div className="h-2 bg-brand-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand-600 rounded-full bar-fill"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            ) : (
              <button
                type="submit"
                disabled={!file}
                className="btn-primary w-full py-4 rounded-xl text-base flex items-center justify-center gap-3
                           disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 12h4l3-9 5 18 3-9h5"/>
                </svg>
                Analyze Scan
              </button>
            )}
          </div>

        </form>
      </div>
    </div>
  )
}
