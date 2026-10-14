import { AnimatePresence, motion } from 'framer-motion'
import { Check, Loader2 } from 'lucide-react'

const STAGES = [
  'Scanning files',
  'Parsing Python sources',
  'Indexing symbols',
  'Resolving routes and application wiring',
  'Resolving calls and resource usage',
  'Mapping tests to components',
  'Reading dependency manifests',
  'Computing graph metrics',
  'Generating findings',
]

/** Live view of a real analysis run: stages come from the backend as they happen. */
export default function AnalysisProgress({ run, upload }) {
  const done = new Set((run?.stages || []).map((s) => s.stage))
  const completed = run?.status === 'completed'
  const progress = completed ? 1 : run?.progress || 0
  const summary = run?.summary || {}
  return (
    <div>
      {upload > 0 && upload < 1 && !run && <div className="mb-3 text-xs text-ink-300">Uploading… {Math.round(upload * 100)}%</div>}
      <div className="h-1.5 overflow-hidden rounded-full bg-ink-700">
        <motion.div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400" animate={{ width: `${Math.max(4, progress * 100)}%` }} transition={{ duration: 0.4 }} />
      </div>
      <ul className="mt-4 space-y-1.5">
        {STAGES.map((stage, i) => {
          const isDone = completed || done.has(stage) && run?.stage !== stage
          const active = !completed && run?.stage === stage
          const reached = isDone || active
          return (
            <motion.li
              key={stage}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: reached ? 1 : 0.4, x: 0 }}
              transition={{ delay: i * 0.03 }}
              className="flex items-center gap-2.5 text-sm"
            >
              <span className={`flex h-5 w-5 items-center justify-center rounded-full ${isDone ? 'bg-emerald-400/15 text-emerald-300' : active ? 'bg-violet-400/15 text-violet-200' : 'bg-ink-700 text-ink-500'}`}>
                {isDone ? <Check className="h-3 w-3" /> : active ? <Loader2 className="h-3 w-3 animate-spin" /> : <span className="h-1 w-1 rounded-full bg-current" />}
              </span>
              <span className={reached ? 'text-ink-100' : 'text-ink-400'}>{stage}</span>
            </motion.li>
          )
        })}
      </ul>
      <AnimatePresence>
        {completed && summary.scan && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-4 grid grid-cols-3 gap-2 text-center">
            {[
              ['Files', summary.scan.file_count],
              ['Components', Object.values(summary.component_counts || {}).reduce((a, b) => a + b, 0)],
              ['Findings', summary.findings],
            ].map(([k, v]) => (
              <div key={k} className="rounded-lg border border-white/[0.06] bg-ink-900/60 py-2">
                <div className="text-lg font-semibold tabular-nums text-ink-100">{v}</div>
                <div className="text-[11px] uppercase tracking-wider text-ink-400">{k}</div>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
