import { motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'

const VARIANTS = {
  primary: 'bg-violet-500 text-white hover:bg-violet-400 shadow-[0_8px_30px_-10px_rgba(139,92,246,0.8)]',
  secondary: 'bg-ink-700 text-ink-100 hover:bg-ink-600 border border-ink-600',
  ghost: 'text-ink-200 hover:bg-ink-700/70 hover:text-ink-100',
  danger: 'bg-rose-500/15 text-rose-200 border border-rose-500/30 hover:bg-rose-500/25',
  cyan: 'bg-cyan-400 text-ink-950 hover:bg-cyan-300 shadow-[0_8px_30px_-10px_rgba(34,211,238,0.7)]',
}
const SIZES = { sm: 'h-8 px-3 text-xs gap-1.5', md: 'h-9 px-4 text-sm gap-2', lg: 'h-11 px-5 text-sm gap-2' }

export function Button({ variant = 'secondary', size = 'md', icon: Icon, loading, disabled, className = '', children, ...props }) {
  return (
    <motion.button
      whileTap={disabled || loading ? undefined : { scale: 0.97 }}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70 disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : Icon ? <Icon className="h-4 w-4" /> : null}
      {children}
    </motion.button>
  )
}

export function IconButton({ icon: Icon, label, className = '', ...props }) {
  return (
    <motion.button
      whileTap={{ scale: 0.92 }}
      aria-label={label}
      title={label}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-lg text-ink-300 transition-colors hover:bg-ink-700 hover:text-ink-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70 ${className}`}
      {...props}
    >
      <Icon className="h-4 w-4" />
    </motion.button>
  )
}
