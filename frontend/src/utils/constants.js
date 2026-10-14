import {
  AppWindow, Boxes, Braces, Cpu, Database, FileCode2, FlaskConical, Globe, KeyRound, Route,
} from 'lucide-react'

/** Visual identity for each component type returned by the analyzer. */
export const NODE_TYPES = {
  route: { label: 'HTTP route', color: '#22d3ee', icon: Route },
  app: { label: 'Application', color: '#a78bfa', icon: AppWindow },
  function: { label: 'Function', color: '#94a3b8', icon: Braces },
  class: { label: 'Class', color: '#818cf8', icon: Boxes },
  module: { label: 'Module', color: '#64748b', icon: FileCode2 },
  database: { label: 'Database', color: '#fbbf24', icon: Database },
  external_api: { label: 'External API', color: '#fb7185', icon: Globe },
  env_var: { label: 'Env variable', color: '#a3e635', icon: KeyRound },
  worker: { label: 'Background worker', color: '#fb923c', icon: Cpu },
  test: { label: 'Test', color: '#2dd4bf', icon: FlaskConical },
}

export const EDGE_LABELS = {
  calls: 'calls',
  handled_by: 'handled by',
  served_by: 'served by',
  runs_on_startup: 'runs on startup',
  uses_database: 'uses database',
  calls_http: 'calls HTTP',
  reads_env: 'reads env',
  exercises: 'exercises',
  contains: 'contains',
  imports: 'imports',
  runs_worker: 'runs worker',
}

export const PROPAGATING = ['calls', 'handled_by', 'served_by', 'runs_on_startup', 'uses_database', 'calls_http', 'reads_env', 'exercises']

export const SEVERITY = {
  high: { label: 'High', cls: 'text-rose-300 bg-rose-500/10 border-rose-500/25' },
  medium: { label: 'Medium', cls: 'text-amber-300 bg-amber-500/10 border-amber-500/25' },
  low: { label: 'Low', cls: 'text-sky-300 bg-sky-500/10 border-sky-500/25' },
  info: { label: 'Info', cls: 'text-ink-300 bg-ink-700 border-ink-600' },
}

export const EXPERIMENT_STATUS = {
  prediction_only: { label: 'Prediction only', cls: 'text-violet-300 bg-violet-500/10 border-violet-500/25' },
  queued: { label: 'Queued', cls: 'text-cyan-300 bg-cyan-500/10 border-cyan-500/25' },
  running: { label: 'Running', cls: 'text-cyan-300 bg-cyan-500/10 border-cyan-500/25' },
  experiment_executed: { label: 'Experiment executed', cls: 'text-cyan-300 bg-cyan-500/10 border-cyan-500/25' },
  prediction_confirmed: { label: 'Prediction confirmed', cls: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/25' },
  partially_confirmed: { label: 'Partially confirmed', cls: 'text-amber-300 bg-amber-500/10 border-amber-500/25' },
  prediction_contradicted: { label: 'Prediction contradicted', cls: 'text-rose-300 bg-rose-500/10 border-rose-500/25' },
  inconclusive: { label: 'Inconclusive', cls: 'text-ink-200 bg-ink-700 border-ink-500' },
  blocked: { label: 'Blocked', cls: 'text-orange-300 bg-orange-500/10 border-orange-500/25' },
  failed: { label: 'Execution failed', cls: 'text-rose-300 bg-rose-500/10 border-rose-500/25' },
}

export const SCENARIO_ICONS = { db_unavailable: Database, external_api_unavailable: Globe, missing_env_var: KeyRound, worker_unavailable: Cpu }

