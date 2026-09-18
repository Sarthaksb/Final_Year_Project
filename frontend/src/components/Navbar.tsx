import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store'

const PATIENT_LINKS = [
  { to: '/upload',  label: 'New Scan' },
  { to: '/history', label: 'My History' },
]

const DOCTOR_LINKS = [
  { to: '/doctor', label: 'Dashboard' },
]

// Brain/dermatology SVG icon
const LogoIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="text-white">
    <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-1.07-4.27A3 3 0 1 1 9.5 2Z"/>
    <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 1.07-4.27A3 3 0 1 0 14.5 2Z"/>
  </svg>
)

export default function Navbar() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  const links = user?.role === 'doctor' ? DOCTOR_LINKS : PATIENT_LINKS
  const isLanding = location.pathname === '/'

  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 h-16 flex items-center
      bg-white border-b border-gray-200 shadow-sm
      transition-all duration-300`}
    >
      <div className="max-w-7xl mx-auto w-full px-6 flex items-center justify-between">

        {/* ── Logo ──────────────────────────────────────── */}
        <Link
          to={user ? (user.role === 'doctor' ? '/doctor' : '/upload') : '/'}
          className="flex items-center gap-2.5 group flex-shrink-0"
        >
          <div className="w-9 h-9 rounded-xl bg-brand-600
                           flex items-center justify-center
                           shadow-md shadow-blue-200
                           group-hover:shadow-blue-300 group-hover:scale-105
                           transition-all duration-200">
            <LogoIcon />
          </div>
          <span className="font-bold text-gray-900 text-[16px] tracking-tight">
            Derma<span className="text-brand-600">AI</span>
          </span>
        </Link>

        {/* ── Landing public nav ─────────────────────────── */}
        {isLanding && !user && (
          <div className="hidden md:flex items-center gap-6">
            {['Home', 'About', 'Features', 'How It Works'].map(label => (
              <a
                key={label}
                href="#"
                className={`text-sm font-medium transition-colors
                  ${label === 'Home' ? 'text-brand-600 border-b-2 border-brand-600 pb-0.5' : 'text-gray-600 hover:text-gray-900'}`}
              >
                {label}
              </a>
            ))}
          </div>
        )}

        {/* ── Authenticated nav ───────────────────────────── */}
        {user && (
          <div className="hidden sm:flex items-center gap-1">
            {links.map(({ to, label }) => {
              const active = location.pathname === to || location.pathname.startsWith(to + '/')
              return (
                <Link
                  key={to}
                  to={to}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    active
                      ? 'bg-brand-50 text-brand-600 font-semibold'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  }`}
                >
                  {label}
                </Link>
              )
            })}
          </div>
        )}

        {/* ── Right: user + auth ────────────────────────── */}
        <div className="flex items-center gap-3">
          {user ? (
            <>
              {/* Avatar + name */}
              <div className="hidden sm:flex items-center gap-2.5 pr-3
                               border-r border-gray-200">
                <div className="relative">
                  <div className="w-8 h-8 rounded-full bg-brand-600
                                   flex items-center justify-center text-sm font-bold text-white">
                    {user.full_name.charAt(0).toUpperCase()}
                  </div>
                  <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-500
                                    rounded-full border-2 border-white" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-900 leading-none">{user.full_name}</div>
                  <div className="text-[10px] text-gray-400 capitalize mt-0.5">{user.role}</div>
                </div>
              </div>

              <button
                onClick={() => { logout(); navigate('/') }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs
                            text-gray-500 border border-gray-200
                            hover:text-gray-800 hover:border-gray-300 hover:bg-gray-50
                            transition-all"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/>
                  <polyline points="16 17 21 12 16 7"/>
                  <line x1="21" y1="12" x2="9" y2="12"/>
                </svg>
                Sign out
              </button>
            </>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                to="/login"
                className="px-4 py-2 rounded-lg text-sm font-medium text-gray-700
                           hover:text-gray-900 hover:bg-gray-100 transition-all"
              >
                Sign In
              </Link>
              <Link
                to="/register"
                className="btn-primary px-5 py-2 rounded-lg text-sm"
              >
                Get Started
              </Link>
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}
