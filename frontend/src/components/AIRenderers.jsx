import { List, Refs } from './AIPanel'
import { Badge } from './ui'

const CONF = { high: 'text-emerald-300 border-emerald-400/25 bg-emerald-400/10', medium: 'text-amber-200 border-amber-400/25 bg-amber-400/10', low: 'text-rose-300 border-rose-400/25 bg-rose-400/10' }

export function ArchitectureResult({ r }) {
  return (
    <div>
      <p className="text-sm leading-relaxed text-ink-200">{r.summary}</p>
      {r.layers?.length > 0 && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {r.layers.map((l, i) => (
            <div key={i} className="rounded-lg border border-white/[0.06] bg-ink-900/50 p-3">
              <div className="text-sm font-medium text-ink-100">{l.name}</div>
              <div className="mt-0.5 text-xs text-ink-300">{l.role}</div>
              <div className="mt-2 flex flex-wrap gap-1">
                {l.components.slice(0, 6).map((c) => (
                  <span key={c} className="rounded bg-ink-700 px-1.5 py-0.5 font-mono text-[10px] text-ink-200">{c.replace(/^\w+:/, '')}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      {r.key_flows?.map((f, i) => (
        <div key={i} className="mt-3">
          <div className="text-xs font-medium uppercase tracking-wider text-ink-400">{f.name}</div>
          <ol className="mt-1 space-y-0.5 text-sm text-ink-200">
            {f.steps.map((s, j) => (
              <li key={j} className="flex gap-2">
                <span className="font-mono text-xs text-cyan-300">{j + 1}.</span>
                {s}
              </li>
            ))}
          </ol>
        </div>
      ))}
      <List title="Risks" items={r.risks} />
      <List title="Unknowns (not determinable statically)" items={r.unknowns} tone="text-ink-300" />
      <Refs refs={r.evidence_used} />
    </div>
  )
}

export function FailureAnalysisResult({ r }) {
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm leading-relaxed text-ink-200">{r.summary}</p>
        <Badge className={CONF[r.confidence]}>confidence: {r.confidence}</Badge>
      </div>
      <div className="mt-3 rounded-lg border border-white/[0.06] bg-ink-900/50 p-3 text-sm text-ink-200">
        <div className="mb-1 text-xs font-medium uppercase tracking-wider text-ink-400">Failure mechanism</div>
        {r.failure_mechanism}
      </div>
      {r.user_impact && <p className="mt-3 text-sm text-ink-300"><span className="font-medium text-ink-100">User impact:</span> {r.user_impact}</p>}
      <List title="Predicted symptoms" items={r.predicted_symptoms} />
      <List title="Assumptions" items={r.assumptions} tone="text-ink-300" />
      <List title="Uncertainties" items={r.uncertainties} tone="text-amber-100/80" />
      <List title="Recommended tests" items={r.recommended_tests} />
      <List title="Mitigations" items={r.mitigations} />
      <Refs refs={r.evidence_used} />
    </div>
  )
}

export function InterpretationResult({ r }) {
  return (
    <div>
      <p className="text-sm leading-relaxed text-ink-200">{r.verdict_explanation}</p>
      <List title="Agreements" items={r.agreements} />
      <List title="Discrepancies" items={r.discrepancies} tone="text-amber-100/90" />
      <List title="Lessons" items={r.lessons} />
      {r.next_test && (
        <div className="mt-3 rounded-lg border border-cyan-400/20 bg-cyan-400/[0.05] p-3 text-sm text-cyan-50/90">
          <span className="font-medium">Next test: </span>
          {r.next_test}
        </div>
      )}
      <List title="Caveats" items={r.caveats} tone="text-ink-300" />
      <Refs refs={r.evidence_used} />
    </div>
  )
}
