import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'
import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { drawer, fade, modal } from '../../animations/variants'
import { IconButton } from './Button'

function useEscape(open, onClose) {
  useEffect(() => {
    if (!open) return undefined
    const h = (e) => e.key === 'Escape' && onClose?.()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])
}

export function Modal({ open, onClose, title, subtitle, children, footer, width = 'max-w-lg' }) {
  useEscape(open, onClose)
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-center justify-center p-4" initial="initial" animate="animate" exit="exit">
          <motion.div variants={fade} className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            variants={modal}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            className={`relative flex max-h-[90vh] w-full ${width} flex-col overflow-hidden rounded-2xl border border-white/10 bg-ink-850 shadow-2xl`}
          >
            <div className="flex items-start justify-between gap-3 border-b border-white/[0.06] px-5 py-4">
              <div>
                <h2 className="text-base font-semibold text-ink-100">{title}</h2>
                {subtitle && <p className="mt-0.5 text-sm text-ink-300">{subtitle}</p>}
              </div>
              <IconButton icon={X} label="Close" onClick={onClose} />
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
            {footer && <div className="flex items-center justify-end gap-2 border-t border-white/[0.06] px-5 py-3">{footer}</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}

export function Drawer({ open, onClose, title, subtitle, children, width = 'max-w-xl', icon: Icon }) {
  useEscape(open, onClose)
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-40" initial="initial" animate="animate" exit="exit">
          <motion.div variants={fade} className="absolute inset-0 bg-black/40" onClick={onClose} />
          <motion.aside
            variants={drawer}
            role="dialog"
            aria-label={title}
            className={`absolute right-0 top-0 flex h-full w-full ${width} flex-col border-l border-white/10 bg-ink-850 shadow-2xl`}
          >
            <div className="flex items-start justify-between gap-3 border-b border-white/[0.06] px-5 py-4">
              <div className="flex min-w-0 items-center gap-2.5">
                {Icon && <Icon className="h-4 w-4 shrink-0 text-violet-300" />}
                <div className="min-w-0">
                  <h2 className="truncate text-base font-semibold text-ink-100">{title}</h2>
                  {subtitle && <p className="truncate text-xs text-ink-300">{subtitle}</p>}
                </div>
              </div>
              <IconButton icon={X} label="Close" onClick={onClose} />
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}
