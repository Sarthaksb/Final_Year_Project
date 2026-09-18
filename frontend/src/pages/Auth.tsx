import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { loginApi, registerApi } from '../api/auth'
import { useAuthStore } from '../store'
import { useToast } from '../components/Toast'

interface Props { mode: 'login' | 'register' }

const EyeIcon = ({ open }: { open: boolean }) => open ? (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/>
    <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/>
    <line x1="1" y1="1" x2="23" y2="23"/>
  </svg>
) : (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12S5 4 12 4s11 8 11 8-4 8-11 8S1 12 1 12z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
)

const FEATURES = [
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="text-brand-600">
        <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-1.07-4.27A3 3 0 1 1 9.5 2Z"/>
        <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 1.07-4.27A3 3 0 1 0 14.5 2Z"/>
      </svg>
    ),
    title: 'EfficientNet-B0 Classifier',
    desc: '25,331 ISIC images · 8 dermoscopic classes',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="text-amber-500">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
      </svg>
    ),
    title: 'Real-time Urgency Triage',
    desc: 'HIGH / MEDIUM / LOW instant routing',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-500">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
      </svg>
    ),
    title: 'RAG-Grounded Explanations',
    desc: 'ChromaDB vector store · cited medical text',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="text-rose-500">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
      </svg>
    ),
    title: 'Doctor Review & PDF Report',
    desc: 'Expert override · signed clinical reports',
  },
]

export default function Auth({ mode }: Props) {
  const navigate  = useNavigate()
  const { login, user } = useAuthStore()
  const toast = useToast()

  const [tab, setTab]           = useState<'login' | 'register'>(mode)
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
      setError(msg ?? (tab === 'login' ? 'Invalid email or password.' : 'Registration failed. Email may already be taken.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[calc(100vh-64px)] flex bg-gray-50">

      {/* ── Left panel — features (desktop only) ── */}
      <div className="hidden lg:flex flex-col justify-between w-[420px] flex-shrink-0
                       bg-white border-r border-gray-200 p-12">
        <div>
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5 mb-10 group">
            <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center shadow-md group-hover:scale-105 transition-transform">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-1.07-4.27A3 3 0 1 1 9.5 2Z"/>
                <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 1.07-4.27A3 3 0 1 0 14.5 2Z"/>
              </svg>
            </div>
            <span className="text-xl font-bold text-gray-900">
              Derma<span className="text-brand-600">AI</span>
            </span>
          </Link>

          <h2 className="text-2xl font-bold text-gray-900 mb-2 leading-snug">
            Intelligent Skin Lesion<br />
            <span className="text-brand-600">Diagnostic Platform</span>
          </h2>
          <p className="text-gray-500 text-sm leading-relaxed mb-8">
            AI-powered clinical decision support for dermatology — designed for patients, built for doctors.
          </p>

          <div className="space-y-3">
            {FEATURES.map((f, i) => (
              <div key={i} className="flex items-center gap-3 p-3.5 bg-gray-50 rounded-xl border border-gray-100">
                <div className="w-9 h-9 rounded-lg bg-white border border-gray-100 flex items-center justify-center flex-shrink-0 shadow-sm">
                  {f.icon}
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-900">{f.title}</p>
                  <p className="text-xs text-gray-500">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-3 mt-8">
          {[
            { v: '25K+', l: 'Training images' },
            { v: '8',    l: 'Lesion classes' },
            { v: '>80%', l: 'MEL recall' },
            { v: 'ISIC', l: '2019 dataset' },
          ].map(s => (
            <div key={s.l} className="bg-brand-50 rounded-xl p-3.5 text-center border border-brand-100">
              <div className="text-lg font-black text-brand-700">{s.v}</div>
              <div className="text-[10px] text-brand-500 mt-0.5 font-medium">{s.l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right panel — form ────────────────────────── */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">

          {/* Mobile logo */}
          <div className="lg:hidden text-center mb-8">
            <Link to="/" className="inline-flex items-center gap-2.5">
              <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-1.07-4.27A3 3 0 1 1 9.5 2Z"/>
                  <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 1.07-4.27A3 3 0 1 0 14.5 2Z"/>
                </svg>
              </div>
              <span className="text-xl font-bold text-gray-900">Derma<span className="text-brand-600">AI</span></span>
            </Link>
          </div>

          <div className="mb-8">
            <h1 className="text-2xl font-bold text-gray-900 mb-1">
              {tab === 'login' ? 'Welcome back' : 'Create your account'}
            </h1>
            <p className="text-gray-500 text-sm">
              {tab === 'login'
                ? 'Sign in to access your diagnostic dashboard'
                : 'Get free access to AI-powered skin analysis'}
            </p>
          </div>

          {/* Tab pills */}
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
                <label htmlFor="fullname" className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5">
                  Full Name
                </label>
                <div className="input-icon-wrap">
                  <svg className="input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
                  </svg>
                  <input
                    id="fullname"
                    type="text"
                    required
                    autoComplete="name"
                    value={fullName}
                    onChange={e => setFullName(e.target.value)}
                    placeholder="Dr. Jane Smith"
                    className="input-field"
                  />
                </div>
              </div>
            )}

            <div>
              <label htmlFor="email" className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5">
                Email Address
              </label>
              <div className="input-icon-wrap">
                <svg className="input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>
                </svg>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@hospital.com"
                  className="input-field"
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between mb-1.5">
                <label htmlFor="password" className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Password
                </label>
                {tab === 'login' && (
                  <span className="text-xs text-brand-600">Min. 6 characters</span>
                )}
              </div>
              <div className="input-icon-wrap relative">
                <svg className="input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
                <input
                  id="password"
                  type={showPass ? 'text' : 'password'}
                  required
                  minLength={6}
                  autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
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
                  aria-label={showPass ? 'Hide password' : 'Show password'}
                >
                  <EyeIcon open={showPass} />
                </button>
              </div>
            </div>

            {/* Error message */}
            {error && (
              <div className="flex items-start gap-3 bg-red-50 border border-red-200
                               rounded-xl px-4 py-3 scale-in">
                <div className="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center
                                 text-white text-xs font-bold flex-shrink-0 mt-0.5">✕</div>
                <p className="text-sm text-red-600">{error}</p>
              </div>
            )}

            <button
              type="submit"
              id={tab === 'login' ? 'btn-login' : 'btn-register'}
              disabled={loading}
              className="btn-primary w-full py-3.5 rounded-xl text-sm flex items-center justify-center gap-2 mt-2"
            >
              {loading ? (
                <>
                  <span className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                  {tab === 'login' ? 'Signing in…' : 'Creating account…'}
                </>
              ) : (
                <>
                  {tab === 'login' ? 'Sign In' : 'Create Account'}
                  <span>→</span>
                </>
              )}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            {tab === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button
              type="button"
              onClick={() => { setTab(tab === 'login' ? 'register' : 'login'); setError('') }}
              className="text-brand-600 hover:text-brand-700 font-semibold transition"
            >
              {tab === 'login' ? 'Create account →' : '← Sign in'}
            </button>
          </p>

          <p className="text-center text-[11px] text-gray-400 mt-6 leading-relaxed">
            For research and demonstration purposes only.<br />
            Not a substitute for professional medical advice.
          </p>
        </div>
      </div>
    </div>
  )
}
