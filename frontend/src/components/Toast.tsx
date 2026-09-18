// Toast notification system — light-mode, global, auto-dismiss, accessible
import { useState, useCallback, createContext, useContext, useEffect } from 'react'

type ToastType = 'success' | 'error' | 'info' | 'warning'

interface Toast {
  id: string
  type: ToastType
  message: string
  duration?: number
}

interface ToastCtx {
  success: (msg: string) => void
  error:   (msg: string) => void
  info:    (msg: string) => void
  warning: (msg: string) => void
}

const ToastContext = createContext<ToastCtx>({
  success: () => {}, error: () => {}, info: () => {}, warning: () => {},
})

export function useToast() { return useContext(ToastContext) }

const ICONS: Record<ToastType, string> = {
  success: '✓', error: '✕', info: 'ℹ', warning: '⚠',
}
const COLORS: Record<ToastType, string> = {
  success: 'border-emerald-200 bg-white text-emerald-700 shadow-card-md',
  error:   'border-red-200    bg-white text-red-700    shadow-card-md',
  info:    'border-brand-200  bg-white text-brand-700  shadow-card-md',
  warning: 'border-amber-200  bg-white text-amber-700  shadow-card-md',
}
const DOT_COLORS: Record<ToastType, string> = {
  success: 'bg-emerald-500', error: 'bg-red-500', info: 'bg-brand-500', warning: 'bg-amber-500',
}

function ToastItem({ toast, onRemove }: { toast: Toast; onRemove: (id: string) => void }) {
  const [leaving, setLeaving] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => {
      setLeaving(true)
      setTimeout(() => onRemove(toast.id), 280)
    }, toast.duration ?? 4000)
    return () => clearTimeout(timer)
  }, [toast, onRemove])

  return (
    <div
      className={`flex items-start gap-3 px-4 py-3 rounded-xl border
        min-w-[280px] max-w-[380px]
        ${COLORS[toast.type]}
        ${leaving ? 'toast-leave' : 'toast-enter'}`}
      role="alert"
    >
      <div className={`w-5 h-5 rounded-full ${DOT_COLORS[toast.type]} flex items-center
                       justify-center text-white text-xs font-bold flex-shrink-0 mt-0.5`}>
        {ICONS[toast.type]}
      </div>
      <p className="text-sm leading-relaxed flex-1 text-gray-800">{toast.message}</p>
      <button
        onClick={() => { setLeaving(true); setTimeout(() => onRemove(toast.id), 280) }}
        className="text-gray-400 hover:text-gray-600 transition flex-shrink-0 leading-none text-lg"
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  )
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const add = useCallback((type: ToastType, message: string, duration?: number) => {
    const id = crypto.randomUUID()
    setToasts(t => [...t, { id, type, message, duration }])
  }, [])

  const remove = useCallback((id: string) => {
    setToasts(t => t.filter(x => x.id !== id))
  }, [])

  const ctx: ToastCtx = {
    success: (m) => add('success', m),
    error:   (m) => add('error',   m),
    info:    (m) => add('info',    m),
    warning: (m) => add('warning', m),
  }

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      <div
        className="fixed top-20 right-4 z-[100] flex flex-col gap-2"
        aria-live="assertive"
        aria-atomic="false"
      >
        {toasts.map(t => (
          <ToastItem key={t.id} toast={t} onRemove={remove} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}
