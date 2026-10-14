import { motion } from 'framer-motion'
import { SCENARIO_ICONS } from '../utils/constants'
import { shortId } from '../utils/graph'

/** Choose a supported failure scenario and a real discovered component to target. */
export default function ScenarioPicker({ scenarios, scenario, target, onScenario, onTarget }) {
  const current = scenarios.find((s) => s.id === scenario)
  return (
    <div className="space-y-4">
      <div className="grid gap-2 sm:grid-cols-2">
        {scenarios.map((s) => {
          const Icon = SCENARIO_ICONS[s.id]
          const active = s.id === scenario
          return (
            <motion.button
              key={s.id}
              whileHover={s.supported ? { y: -2 } : undefined}
              whileTap={s.supported ? { scale: 0.98 } : undefined}
              disabled={!s.supported}
              onClick={() => onScenario(s.id)}
              aria-pressed={active}
              className={`relative rounded-xl border p-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${active ? 'border-violet-400/50 bg-violet-500/10' : 'border-white/[0.07] bg-ink-900/50 hover:border-white/15'}`}
            >
              <div className="flex items-center gap-2">
                <Icon className={`h-4 w-4 ${active ? 'text-violet-200' : 'text-ink-300'}`} />
                <span className="text-sm font-medium text-ink-100">{s.label}</span>
              </div>
              <p className="mt-1 text-xs text-ink-400">{s.supported ? s.fault : `No ${s.target_types.join('/')} component discovered in this project.`}</p>
            </motion.button>
          )
        })}
      </div>
      {current && (
        <div>
          <label htmlFor="target" className="text-xs font-medium uppercase tracking-wider text-ink-400">
            Target component
          </label>
          <select
            id="target"
            value={target || ''}
            onChange={(e) => onTarget(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-ink-600 bg-ink-900 px-3 py-2 text-sm text-ink-100 outline-none focus:border-violet-400"
          >
            <option value="" disabled>Select a discovered component…</option>
            {current.targets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({shortId(t.id)}) · {t.dependents} dependents · criticality {t.criticality}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  )
}
