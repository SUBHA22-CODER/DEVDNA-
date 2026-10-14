import { AnimatePresence, motion } from 'framer-motion'
import {
  Activity, Beaker, ChevronDown, FileText, FlaskConical, Menu, MessageSquareText, Moon, Plus, Radar, Settings, ShieldAlert, Sun, Workflow, X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation, useOutlet } from 'react-router-dom'
import { page } from '../animations/variants'
import ChatDrawer from '../components/ChatDrawer'
import NewProjectModal from '../components/NewProjectModal'
import { useProject } from '../hooks/useProject'
import { useSettings } from '../hooks/useSettings'
import { useStatus } from '../hooks/useStatus'

export const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: Activity },
  { to: '/architecture', label: 'Architecture', icon: Workflow },
  { to: '/prediction', label: 'Failure Prediction', icon: Radar },
  { to: '/lab', label: 'What-If Lab', icon: Beaker },
  { to: '/findings', label: 'Findings', icon: ShieldAlert },
  { to: '/experiments', label: 'Experiments', icon: FlaskConical },
  { to: '/reports', label: 'Reports', icon: FileText },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function ThemeToggle({ className = '' }) {
  const { settings, toggleTheme } = useSettings()
  const isBright = settings.theme === 'bright'

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isBright ? 'Switch to Dark mode' : 'Switch to Bright mode'}
      title={isBright ? 'Switch to Dark mode (Ctrl+Shift+D)' : 'Switch to Bright mode (Ctrl+Shift+D)'}
      className={`relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-ink-800 text-ink-300 transition-colors hover:border-violet-400/30 hover:bg-ink-700 hover:text-ink-100 ${className}`}
    >
      <motion.div
        key={isBright ? 'sun' : 'moon'}
        initial={{ rotate: -45, scale: 0.5, opacity: 0 }}
        animate={{ rotate: 0, scale: 1, opacity: 1 }}
        exit={{ rotate: 45, scale: 0.5, opacity: 0 }}
        transition={{ duration: 0.2 }}
      >
        {isBright ? (
          <Sun className="h-4 w-4 text-amber-500" />
        ) : (
          <Moon className="h-4 w-4 text-violet-300" />
        )}
      </motion.div>
    </button>
  )
}

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500/30 to-cyan-400/20 ring-1 ring-white/10">
        <svg viewBox="0 0 32 32" className="h-5 w-5" aria-hidden>
          <path d="M10 5c0 7 12 7 12 14s-12 0-12 8M22 5c0 7-12 7-12 14s12 0 12 8" fill="none" stroke="#c4b5fd" strokeWidth="2.4" strokeLinecap="round" />
          <path d="M12 11h8M12 21h8" stroke="#67e8f9" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
      </div>
      <div>
        <div className="text-sm font-semibold tracking-tight text-ink-100">DevDNA</div>
        <div className="text-[10px] uppercase tracking-[0.16em] text-ink-400">digital twin</div>
      </div>
    </div>
  )
}

function StatusIndicator() {
  const { backend, ai } = useStatus()
  const backendDot = backend === 'online' ? 'bg-emerald-400' : backend === 'offline' ? 'bg-rose-400' : 'bg-amber-300'
  const aiOk = ai?.configured && ai?.last_check?.available !== false
  const aiDot = !ai ? 'bg-ink-500' : aiOk ? 'bg-violet-400' : ai.configured ? 'bg-amber-300' : 'bg-ink-500'
  return (
    <NavLink to="/settings" className="block rounded-lg border border-white/[0.06] bg-ink-900/60 p-3 text-xs transition-colors hover:border-white/10">
      <div className="flex items-center justify-between">
        <span className="text-ink-300">Backend</span>
        <span className="flex items-center gap-1.5 text-ink-200">
          <span className={`h-1.5 w-1.5 rounded-full ${backendDot} ${backend === 'online' ? 'shadow-[0_0_8px_rgba(52,211,153,0.8)]' : ''}`} />
          {backend}
        </span>
      </div>
      <div className="mt-1.5 flex items-center justify-between gap-2">
        <span className="text-ink-300">Gemma</span>
        <span className="flex min-w-0 items-center gap-1.5 text-ink-200">
          <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${aiDot}`} />
          <span className="truncate">{!ai ? '—' : ai.configured ? (ai.last_check?.available === false ? 'unavailable' : 'configured') : 'not configured'}</span>
        </span>
      </div>
      {ai?.model && <div className="mt-1 truncate font-mono text-[10px] text-ink-400">{ai.model}</div>}
      {ai?.last_request && (
        <div className="mt-0.5 truncate text-[10px] text-ink-400">last request: {ai.last_request.status}</div>
      )}
    </NavLink>
  )
}

function ProjectSelector({ onNew }) {
  const { projects, current, setCurrentId } = useProject()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    const h = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 rounded-lg border border-white/[0.07] bg-ink-800 px-3 py-2 text-left text-sm transition-colors hover:border-white/15"
      >
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-wider text-ink-400">Project</div>
          <div className="truncate text-ink-100">{current?.name || 'No project yet'}</div>
        </div>
        <motion.span animate={{ rotate: open ? 180 : 0 }}>
          <ChevronDown className="h-4 w-4 text-ink-400" />
        </motion.span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.14 }}
            className="absolute left-0 right-0 z-30 mt-1 overflow-hidden rounded-lg border border-white/10 bg-ink-800 shadow-xl"
            role="listbox"
          >
            <div className="max-h-64 overflow-y-auto py-1">
              {projects.map((p) => (
                <button
                  key={p.id}
                  role="option"
                  aria-selected={p.id === current?.id}
                  onClick={() => {
                    setCurrentId(p.id)
                    setOpen(false)
                  }}
                  className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-ink-700 ${p.id === current?.id ? 'text-violet-200' : 'text-ink-200'}`}
                >
                  <span className="truncate">{p.name}</span>
                  <span className="ml-2 shrink-0 text-[10px] uppercase text-ink-400">{p.source_type}</span>
                </button>
              ))}
            </div>
            <button
              onClick={() => {
                setOpen(false)
                onNew()
              }}
              className="flex w-full items-center justify-between border-t border-white/[0.06] px-3 py-2 text-sm text-cyan-200 hover:bg-ink-700"
            >
              <span className="flex items-center gap-2">
                <Plus className="h-4 w-4" /> New project
              </span>
              <kbd className="rounded border border-cyan-400/30 bg-ink-900/60 px-1 py-0.5 font-mono text-[10px] text-cyan-300">⌘K</kbd>
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function NavList({ onNavigate }) {
  return (
    <nav className="space-y-0.5" aria-label="Main">
      {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} end={to === '/'} onClick={onNavigate} className="relative block">
          {({ isActive }) => (
            <div className={`relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${isActive ? 'text-ink-100' : 'text-ink-300 hover:text-ink-100'}`}>
              {isActive && (
                <motion.div layoutId="nav-active" className="absolute inset-0 rounded-lg border border-violet-400/20 bg-violet-500/10" transition={{ type: 'spring', stiffness: 500, damping: 40 }} />
              )}
              {isActive && <motion.span layoutId="nav-bar" className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-gradient-to-b from-violet-400 to-cyan-300" />}
              <Icon className={`relative h-4 w-4 ${isActive ? 'text-violet-300' : ''}`} />
              <span className="relative">{label}</span>
            </div>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

export default function AppLayout() {
  const [newOpen, setNewOpen] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [mobileNav, setMobileNav] = useState(false)
  const { current, ready } = useProject()
  const { toggleTheme } = useSettings()
  const location = useLocation()
  const outlet = useOutlet({ openNewProject: () => setNewOpen(true), openChat: () => setChatOpen(true) })

  useEffect(() => setMobileNav(false), [location.pathname])

  const sidebar = (
    <div className="flex h-full flex-col gap-5 p-4">
      <div className="flex items-center justify-between">
        <Logo />
        <ThemeToggle />
      </div>
      <ProjectSelector onNew={() => setNewOpen(true)} />
      <NavList onNavigate={() => setMobileNav(false)} />
      <div className="mt-auto space-y-3">
        <button
          onClick={() => setChatOpen(true)}
          disabled={!ready}
          className="flex w-full items-center justify-between rounded-lg border border-cyan-400/20 bg-cyan-400/[0.06] px-3 py-2 text-sm text-cyan-100 transition-colors hover:bg-cyan-400/10 disabled:cursor-not-allowed disabled:opacity-40"
          title={ready ? 'Ask questions about the analysed repository (Ctrl/Cmd+J)' : 'Analyse a project first'}
        >
          <span className="flex items-center gap-2">
            <MessageSquareText className="h-4 w-4" /> Ask DevDNA
          </span>
          <kbd className="hidden rounded border border-cyan-400/30 bg-ink-900/60 px-1.5 py-0.5 font-mono text-[10px] text-cyan-300 sm:inline-block">⌘J</kbd>
        </button>
        <StatusIndicator />
      </div>
    </div>
  )

  useEffect(() => {
    const handleKeyDown = (e) => {
      const isInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName) || document.activeElement?.isContentEditable
      if (e.key === 'Escape') {
        setNewOpen(false)
        setChatOpen(false)
        setMobileNav(false)
      } else if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'd') {
        e.preventDefault()
        toggleTheme()
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setNewOpen(true)
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'j') {
        e.preventDefault()
        if (ready) setChatOpen((o) => !o)
      } else if (!isInput && e.key === '/' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        setNewOpen(true)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [ready, toggleTheme])

  return (
    <div className="relative flex h-full">
      <div className="grid-bg pointer-events-none fixed inset-0 opacity-60" />
      <div className="pointer-events-none fixed -top-40 left-1/3 h-80 w-[40rem] rounded-full bg-violet-600/10 blur-3xl" />

      <aside className="relative z-10 hidden w-64 shrink-0 border-r border-white/[0.06] bg-ink-900/80 backdrop-blur lg:block">{sidebar}</aside>

      {/* Mobile top bar + slide-in navigation */}
      <div className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-white/[0.06] bg-ink-900/90 px-4 backdrop-blur lg:hidden">
        <Logo />
        <div className="flex items-center gap-1.5">
          <ThemeToggle />
          <button aria-label="Ask DevDNA" disabled={!ready} onClick={() => setChatOpen(true)} className="rounded-lg p-2 text-cyan-200 disabled:opacity-40">
            <MessageSquareText className="h-5 w-5" />
          </button>
          <button aria-label="Open navigation" onClick={() => setMobileNav(true)} className="rounded-lg p-2 text-ink-200">
            <Menu className="h-5 w-5" />
          </button>
        </div>
      </div>
      <AnimatePresence>
        {mobileNav && (
          <motion.div className="fixed inset-0 z-40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-black/60" onClick={() => setMobileNav(false)} />
            <motion.aside
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 400, damping: 40 }}
              className="absolute left-0 top-0 h-full w-72 border-r border-white/10 bg-ink-900"
            >
              <button aria-label="Close navigation" onClick={() => setMobileNav(false)} className="absolute right-3 top-4 rounded-lg p-1.5 text-ink-300">
                <X className="h-4 w-4" />
              </button>
              {sidebar}
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      <main className="relative z-10 min-w-0 flex-1 overflow-x-hidden overflow-y-auto pt-14 lg:pt-0">
        <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {/* Keyed entrance animation per page (no exit wait, so navigation can never stall) */}
          <motion.div key={location.pathname} variants={page} initial="initial" animate="animate">
            {outlet}
          </motion.div>
        </div>
      </main>

      <NewProjectModal open={newOpen} onClose={() => setNewOpen(false)} />
      {current && <ChatDrawer open={chatOpen} onClose={() => setChatOpen(false)} project={current} />}
    </div>
  )
}
