import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { loginApi, registerApi } from '../api/auth'
import { useAuthStore } from '../store'
import { useToast } from '../components/Toast'

/* ── Icon components ────────────────────────────────────────── */
const ShieldIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-brand-600">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
  </svg>
)

const FEATURE_ICONS = [
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="text-brand-600">
        <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-1.07-4.27A3 3 0 1 1 9.5 2Z"/>
        <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 1.07-4.27A3 3 0 1 0 14.5 2Z"/>
      </svg>
    ),
    title: 'AI Analysis',
    desc: 'Fast and accurate prediction',
    bg: 'bg-blue-50',
    border: 'border-blue-100',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-600">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
    ),
    title: 'Urgency Triage',
    desc: 'Know what needs immediate attention',
    bg: 'bg-emerald-50',
    border: 'border-emerald-100',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="text-violet-600">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
      </svg>
    ),
    title: 'Trusted Explanation',
    desc: 'Knowledge-based insights',
    bg: 'bg-violet-50',
    border: 'border-violet-100',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="text-rose-500">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
      </svg>
    ),
    title: 'Dermatologist Reviewed',
    desc: 'Expert validation for reliability',
    bg: 'bg-rose-50',
    border: 'border-rose-100',
  },
]

const FEATURES = [
  {
    icon: '🔬',
    title: 'EfficientNet-B0 Classifier',
    desc: 'Trained on 25,331 ISIC 2019 images across 8 dermoscopic classes with >80% MEL recall.',
    color: 'from-blue-50 to-blue-50/50',
    border: 'border-blue-100',
    accent: 'text-brand-600',
  },
  {
    icon: '⚡',
    title: 'Agentic Triage',
    desc: 'LangGraph + Gemini orchestrator routes each case — URGENT, FOLLOW-UP, or NORMAL — in real time.',
    color: 'from-amber-50 to-amber-50/50',
    border: 'border-amber-100',
    accent: 'text-amber-600',
  },
  {
    icon: '📚',
    title: 'RAG Explanations',
    desc: 'ChromaDB vector store retrieves grounded medical text, explaining every prediction with a source.',
    color: 'from-emerald-50 to-emerald-50/50',
    border: 'border-emerald-100',
    accent: 'text-emerald-600',
  },
  {
    icon: '🩺',
    title: 'Doctor Dashboard',
    desc: 'Clinicians review AI output, accept or override diagnoses, add notes, and download PDF reports.',
    color: 'from-rose-50 to-rose-50/50',
    border: 'border-rose-100',
    accent: 'text-rose-600',
  },
]

const CLASSES = [
  { code: 'MEL',  name: 'Melanoma',             risk: 'high' },
  { code: 'NV',   name: 'Melanocytic Nevus',     risk: 'low' },
  { code: 'BCC',  name: 'Basal Cell Carcinoma',  risk: 'high' },
  { code: 'AK',   name: 'Actinic Keratosis',     risk: 'medium' },
  { code: 'BKL',  name: 'Benign Keratosis',      risk: 'low' },
  { code: 'DF',   name: 'Dermatofibroma',        risk: 'low' },
  { code: 'VASC', name: 'Vascular Lesion',       risk: 'low' },
  { code: 'SCC',  name: 'Squamous Cell Carcinoma', risk: 'high' },
]

const RISK_BADGE: Record<string, string> = {
  high:   'bg-red-50 text-red-600 border-red-200',
  medium: 'bg-amber-50 text-amber-600 border-amber-200',
  low:    'bg-emerald-50 text-emerald-600 border-emerald-200',
}

/* ── Inline Auth Form (embedded in hero) ────────────────────── */
function HeroAuthForm() {
  const navigate = useNavigate()
  const { login, user } = useAuthStore()
  const toast = useToast()

  const [tab, setTab]           = useState<'login' | 'register'>('register')
  const [fullName, setFullName] = useState('')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')
  const [showPass, setShowPass] = useState(false)

  useEffect(() => {
    if (user) navigate(user.role === 'doctor' ? '/doctor' : '/upload', { replace: true })
  }, [user, navigate])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      let data
      if (tab === 'register') {
        if (!fullName.trim()) { setError('Full name is required'); setLoading(false); return }
        if (password.length < 6) { setError('Password must be at least 6 characters'); setLoading(false); return }
        data = await registerApi(email, password, fullName)
        toast.success(`Welcome, ${data.user.full_name}!`)
      } else {
        data = await loginApi(email, password)
        toast.success(`Welcome back, ${data.user.full_name}!`)
      }
      login(data.access_token, data.user)
      navigate(data.user.role === 'doctor' ? '/doctor' : '/upload', { replace: true })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? (tab === 'login' ? 'Invalid email or password.' : 'Registration failed.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-2xl shadow-card-lg border border-gray-200 p-8 w-full">
      <h2 className="text-xl font-bold text-gray-900 mb-1">
        {tab === 'login' ? 'Welcome back' : 'Create your account'}
      </h2>
      <p className="text-gray-500 text-sm mb-6">
        {tab === 'login'
          ? 'Sign in to your diagnostic dashboard'
          : 'Get free access to AI-powered skin analysis'}
      </p>

      {/* Tab toggle */}
      <div className="flex bg-gray-100 rounded-xl p-1 mb-6 border border-gray-200">
        {(['login', 'register'] as const).map(t => (
          <button
            key={t}
            type="button"
            onClick={() => { setTab(t); setError('') }}
            className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all ${
              tab === t
                ? 'bg-brand-600 text-white shadow-md shadow-blue-200'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {t === 'login' ? 'Sign In' : 'Register'}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {tab === 'register' && (
          <div className="scale-in">
            <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5">
              Full Name
            </label>
            <div className="input-icon-wrap">
              <svg className="input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
              </svg>
              <input
                type="text"
                required
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                placeholder="Dr. Jane Smith"
                className="input-field"
              />
            </div>
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5">
            Email Address
          </label>
          <div className="input-icon-wrap">
            <svg className="input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>
            </svg>
            <input
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@hospital.com"
              className="input-field"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5">
            Password
          </label>
          <div className="input-icon-wrap relative">
            <svg className="input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
            <input
              type={showPass ? 'text' : 'password'}
              required
              minLength={6}
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              className="input-field pr-12"
            />
            <button
              type="button"
              onClick={() => setShowPass(p => !p)}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition"
              tabIndex={-1}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                {showPass
                  ? <><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></>
                  : <><path d="M1 12S5 4 12 4s11 8 11 8-4 8-11 8S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></>
                }
              </svg>
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-3 scale-in">
            <div className="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0 mt-0.5">✕</div>
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="btn-primary w-full py-3.5 rounded-xl text-sm flex items-center justify-center gap-2 mt-1"
        >
          {loading ? (
            <>
              <span className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
              {tab === 'login' ? 'Signing in…' : 'Creating account…'}
            </>
          ) : (
            <>{tab === 'login' ? 'Sign In' : 'Create Account'} →</>
          )}
        </button>
      </form>

      <p className="text-center text-sm text-gray-500 mt-4">
        {tab === 'login' ? "Don't have an account? " : 'Already have an account? '}
        <button
          type="button"
          onClick={() => { setTab(tab === 'login' ? 'register' : 'login'); setError('') }}
          className="text-brand-600 hover:text-brand-700 font-semibold"
        >
          {tab === 'login' ? 'Create account →' : '← Sign in'}
        </button>
      </p>
    </div>
  )
}

/* ═══════════════ MAIN LANDING PAGE ════════════════════════════ */
export default function Landing() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-gray-50">

      {/* ═══════════ HERO — split layout ═══════════════════════ */}
      <section className="max-w-7xl mx-auto px-6 py-16 lg:py-20">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">

          {/* Left: Hero Content */}
          <div className="page-enter">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full
                            border border-brand-200 bg-brand-50 mb-6">
              <ShieldIcon />
              <span className="text-xs font-semibold text-brand-700 tracking-wide">
                Smarter Skin Care · AI Powered
              </span>
            </div>

            {/* Headline */}
            <h1 className="text-4xl sm:text-5xl font-black text-gray-900 leading-tight mb-5">
              AI-Powered{' '}
              <span className="text-brand-600">Smart Dermatology</span>{' '}
              Diagnostic System
            </h1>

            <p className="text-lg text-gray-600 leading-relaxed mb-8 max-w-lg">
              Upload a skin lesion image, get an instant AI prediction,
              urgency triage, and knowledge-grounded explanation —
              reviewed by a qualified dermatologist.
            </p>

            {/* Skin image with floating AI prediction card */}
            <div className="relative w-full max-w-md mb-10">
              <div className="rounded-2xl overflow-hidden bg-gradient-to-br from-amber-50 to-orange-50 border border-gray-200 shadow-card-md p-4 flex justify-center">
                {/* Placeholder skin image using CSS art */}
                <div className="w-48 h-48 rounded-2xl bg-gradient-to-br from-amber-200 via-orange-200 to-amber-300 relative shadow-inner flex items-center justify-center">
                  <div className="w-16 h-16 rounded-full bg-amber-700/60 shadow-lg" />
                  <div className="absolute inset-0 rounded-2xl bg-gradient-to-tl from-transparent via-white/10 to-white/20" />
                </div>
              </div>

              {/* Floating AI prediction card */}
              <div className="absolute bottom-4 right-0 translate-x-4 bg-white rounded-xl shadow-card-lg border border-gray-200 p-4 w-52 float-card">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-bold text-gray-900">AI Prediction</span>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 text-[10px] font-bold border border-emerald-200">
                    Benign
                  </span>
                </div>
                <div className="space-y-2">
                  {[
                    { icon: '👤', label: 'Probability', value: '92%', color: 'text-gray-700' },
                    { icon: '📍', label: 'Urgency',     value: 'Low', color: 'text-emerald-600' },
                    { icon: 'ℹ️',  label: 'Recommendation', value: 'Monitor', color: 'text-gray-500' },
                  ].map(row => (
                    <div key={row.label} className="flex items-center justify-between text-xs">
                      <span className="text-gray-500 flex items-center gap-1.5">
                        <span className="text-sm">{row.icon}</span> {row.label}
                      </span>
                      <span className={`font-semibold ${row.color}`}>{row.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 4 feature icons */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
              {FEATURE_ICONS.map((f, i) => (
                <div key={i} className={`flex flex-col items-center text-center p-3 rounded-xl border ${f.bg} ${f.border}`}>
                  <div className="w-10 h-10 rounded-lg bg-white border border-white shadow-sm flex items-center justify-center mb-2">
                    {f.icon}
                  </div>
                  <p className="text-xs font-bold text-gray-900 mb-0.5">{f.title}</p>
                  <p className="text-[10px] text-gray-500 leading-tight">{f.desc}</p>
                </div>
              ))}
            </div>

            {/* Tagline */}
            <p className="text-gray-500 italic text-base font-medium">
              Better skin care. <em className="not-italic text-brand-600 font-semibold">Informed decisions.</em>
            </p>
          </div>

          {/* Right: Inline Auth Form */}
          <div className="page-enter" style={{ animationDelay: '100ms' }}>
            <HeroAuthForm />
          </div>
        </div>
      </section>

      {/* ═══════════ FEATURES SECTION ══════════════════════════ */}
      <section className="py-20 px-6 bg-white border-t border-gray-100">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <p className="text-xs font-semibold text-brand-600 uppercase tracking-widest mb-3">
              How it works
            </p>
            <h2 className="text-3xl font-bold text-gray-900">End-to-end AI pipeline</h2>
            <p className="text-gray-500 mt-3 max-w-xl mx-auto text-sm leading-relaxed">
              From raw image upload to a clinical PDF report — every step is automated, explainable, and doctor-reviewed.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {FEATURES.map((f, i) => (
              <div
                key={f.title}
                className={`rounded-2xl p-6 border ${f.border} bg-gradient-to-br ${f.color}
                             hover:shadow-card-md hover:-translate-y-0.5 transition-all duration-300`}
                style={{ animationDelay: `${i * 80}ms` }}
              >
                <div className="text-3xl mb-4">{f.icon}</div>
                <h3 className={`font-bold text-sm mb-2 ${f.accent}`}>{f.title}</h3>
                <p className="text-xs text-gray-600 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════ PIPELINE FLOW ════════════════════════════ */}
      <section className="py-16 px-6 bg-gray-50 border-t border-gray-100">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-10">
            Diagnostic Pipeline
          </h2>
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            {[
              { step: '01', title: 'Upload', desc: 'Image + symptoms', icon: '📷' },
              { step: '02', title: 'Classify', desc: 'EfficientNet-B0', icon: '🧠' },
              { step: '03', title: 'Triage', desc: 'HIGH/MED/LOW', icon: '⚡' },
              { step: '04', title: 'Explain', desc: 'Gemini + RAG', icon: '📚' },
              { step: '05', title: 'Review', desc: 'Doctor signs off', icon: '🩺' },
            ].map((s, i, arr) => (
              <div key={s.step} className="flex items-center gap-4">
                <div className="flex flex-col items-center text-center">
                  <div className="w-14 h-14 bg-white border border-gray-200 rounded-2xl flex items-center justify-center
                                   text-2xl mb-2 shadow-card
                                   hover:border-brand-300 hover:shadow-brand/10 hover:scale-110
                                   transition-all duration-200">
                    {s.icon}
                  </div>
                  <div className="text-[10px] font-bold text-brand-600 mb-0.5">{s.step}</div>
                  <div className="text-xs font-semibold text-gray-900">{s.title}</div>
                  <div className="text-[11px] text-gray-400">{s.desc}</div>
                </div>
                {i < arr.length - 1 && (
                  <div className="hidden sm:block text-gray-300 text-xl flex-shrink-0">→</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════ 8 CLASSES ════════════════════════════════ */}
      <section className="py-20 px-6 bg-white border-t border-gray-100">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">8 Dermoscopic Classes</h2>
            <p className="text-gray-500 text-sm">Trained on ISIC 2019 — 25,331 clinical dermoscopy images</p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {CLASSES.map(c => (
              <div key={c.code} className="bg-white border border-gray-200 rounded-xl p-4 flex flex-col gap-2 shadow-card hover:shadow-card-md hover:-translate-y-0.5 transition-all">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-gray-900 text-sm">{c.code}</span>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${RISK_BADGE[c.risk]}`}>
                    {c.risk}
                  </span>
                </div>
                <p className="text-xs text-gray-500">{c.name}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════ CTA SECTION ══════════════════════════════ */}
      <section className="py-20 px-6 bg-gray-50 border-t border-gray-100">
        <div className="max-w-2xl mx-auto text-center bg-white rounded-3xl p-12 border border-gray-200 shadow-card-md">
          <div className="w-14 h-14 bg-brand-50 border border-brand-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="text-brand-600">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-3">
            Ready to try <span className="text-brand-600">DermaAI</span>?
          </h2>
          <p className="text-gray-500 mb-8 text-sm leading-relaxed">
            Create a free patient account to upload your first scan,
            or contact your clinic admin for doctor-level access.
          </p>
          <div className="flex gap-4 justify-center">
            <Link
              to="/register"
              className="btn-primary px-8 py-3 rounded-xl text-sm font-semibold"
            >
              Create Account →
            </Link>
            <Link
              to="/login"
              className="btn-secondary px-8 py-3 rounded-xl text-sm"
            >
              Sign In
            </Link>
          </div>
        </div>
      </section>

      {/* ═══════════ FOOTER ════════════════════════════════════ */}
      <footer className="border-t border-gray-200 py-8 px-6 text-center bg-white">
        <div className="flex items-center justify-center gap-2 mb-3">
          <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-1.07-4.27A3 3 0 1 1 9.5 2Z"/>
              <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 1.07-4.27A3 3 0 1 0 14.5 2Z"/>
            </svg>
          </div>
          <span className="font-bold text-gray-900 text-sm">
            Derma<span className="text-brand-600">AI</span>
          </span>
        </div>
        <p className="text-xs text-gray-400">
          AI-Powered Smart Dermatology Diagnostic System · Final Year Project<br />
          For research and demonstration only. Not a substitute for professional medical advice.
        </p>
      </footer>
    </div>
  )
}
