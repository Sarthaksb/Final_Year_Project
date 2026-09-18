// UrgencyBadge — light-mode: shows HIGH / MEDIUM / LOW with color, dot, and optional pulse animation

interface Props {
  urgency: 'HIGH' | 'MEDIUM' | 'LOW' | string
  size?: 'sm' | 'md' | 'lg'
  animate?: boolean
}

const CONFIG = {
  HIGH: {
    bg: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-red-200',
    dot: 'bg-red-500',
    pulse: 'urgency-high',
    label: 'HIGH',
  },
  MEDIUM: {
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-amber-200',
    dot: 'bg-amber-400',
    pulse: 'urgency-medium',
    label: 'MEDIUM',
  },
  LOW: {
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
    dot: 'bg-emerald-500',
    pulse: '',
    label: 'LOW',
  },
} as const

const SIZE = {
  sm: 'text-[10px] px-2 py-0.5',
  md: 'text-xs px-2.5 py-1',
  lg: 'text-sm px-3.5 py-1.5 font-bold',
}

export default function UrgencyBadge({ urgency, size = 'md', animate = true }: Props) {
  const key = urgency?.toUpperCase() as keyof typeof CONFIG
  const cfg = CONFIG[key] ?? CONFIG.LOW

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-semibold
        ${cfg.bg} ${cfg.text} ${cfg.border} ${SIZE[size]}
        ${animate ? cfg.pulse : ''}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot} flex-shrink-0`} />
      {cfg.label}
    </span>
  )
}
