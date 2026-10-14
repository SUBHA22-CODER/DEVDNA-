import { motion } from 'framer-motion'
import { ArrowRight, FlaskConical, GitCompareArrows, Radar, ScanSearch, Sparkles, UploadCloud, Workflow } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { item, stagger } from '../animations/variants'
import { useAnalysisFlow } from '../hooks/useAnalysisFlow'
import { useStatus } from '../hooks/useStatus'
import AnalysisProgress from './AnalysisProgress'
import { ErrorState, InlineNotice } from './ui'

export const WORKFLOW = [
  { key: 'discover', label: 'Discover', icon: ScanSearch, text: 'Static AST analysis of real source code' },
  { key: 'visualize', label: 'Visualize', icon: Workflow, text: 'Interactive, evidence-backed graph' },
  { key: 'predict', label: 'Predict', icon: Radar, text: 'Deterministic blast radius + Gemma 4' },
  { key: 'experiment', label: 'Experiment', icon: FlaskConical, text: 'Approved fault injection in a sandbox' },
  { key: 'compare', label: 'Compare', icon: GitCompareArrows, text: 'Prediction vs. observed reality' },
]

/** First screen: two clear actions, analyse a repository or explore the demo. */
export default function Welcome({ onAnalyse }) {
  const flow = useAnalysisFlow()
  const status = useStatus()
  const navigate = useNavigate()

  const demo = async () => {
    const res = await flow.start('sample')
    if (res) navigate('/')
  }

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="mx-auto max-w-5xl py-6 lg:py-12">
      <motion.div variants={item} className="text-center">
        <div className="mx-auto mb-4 inline-flex items-center gap-2 rounded-full border border-violet-400/20 bg-violet-400/[0.07] px-3 py-1 text-xs text-violet-200">
          <Sparkles className="h-3.5 w-3.5" /> Powered by Gemma 4 · open-source AI
        </div>
        <h1 className="text-balance text-4xl font-semibold tracking-tight text-ink-100 sm:text-5xl">
          The digital twin for your <span className="bg-gradient-to-r from-violet-300 to-cyan-300 bg-clip-text text-transparent">software system</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-balance text-ink-300">
          DevDNA maps your architecture from source code, predicts what breaks when a dependency fails, then proves or disproves the prediction with a controlled experiment.
        </p>
      </motion.div>

      {status.backend === 'offline' && (
        <motion.div variants={item} className="mx-auto mt-6 max-w-xl">
          <InlineNotice tone="warn">The backend is not reachable. Start it with <code className="font-mono">uvicorn app.main:app --port 8000</code> in the backend folder.</InlineNotice>
        </motion.div>
      )}

      <motion.div variants={item} className="mt-10 grid gap-4 md:grid-cols-2">
        <motion.button
          whileHover={{ y: -3 }}
          whileTap={{ scale: 0.99 }}
          onClick={onAnalyse}
          className="group rounded-2xl border border-white/[0.07] bg-ink-850/80 p-6 text-left transition-colors hover:border-violet-400/40"
        >
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-violet-500/15 text-violet-200 ring-1 ring-violet-400/20">
            <UploadCloud className="h-5 w-5" />
          </div>
          <h2 className="mt-4 text-lg font-semibold text-ink-100">Analyse a Repository</h2>
          <p className="mt-1 text-sm text-ink-300">Upload a ZIP of a Python project or point to an allowed local folder. Secrets and generated files are skipped.</p>
          <div className="mt-4 flex items-center gap-1 text-sm text-violet-200">
            Choose source <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </div>
        </motion.button>
        <motion.button
          whileHover={{ y: -3 }}
          whileTap={{ scale: 0.99 }}
          onClick={demo}
          disabled={flow.busy}
          className="group rounded-2xl border border-cyan-400/20 bg-gradient-to-br from-cyan-400/[0.07] to-violet-500/[0.05] p-6 text-left transition-colors hover:border-cyan-300/50 disabled:cursor-wait glow-cyan"
        >
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-400/15 text-cyan-200 ring-1 ring-cyan-400/25">
            <Sparkles className="h-5 w-5" />
          </div>
          <h2 className="mt-4 text-lg font-semibold text-ink-100">Explore Demo Project</h2>
          <p className="mt-1 text-sm text-ink-300">ShopLite: a FastAPI shop with SQLite, an external shipping API, a background worker and a real pytest suite. Works offline, no API key needed.</p>
          {flow.busy || flow.run ? (
            <div className="mt-4" onClick={(e) => e.stopPropagation()}>
              <AnalysisProgress run={flow.run} />
            </div>
          ) : (
            <div className="mt-4 flex items-center gap-1 text-sm text-cyan-200">
              Load and analyse <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </div>
          )}
        </motion.button>
      </motion.div>
      {flow.error && (
        <div className="mt-4">
          <ErrorState title="Could not load the demo" error={flow.error} onRetry={demo} />
        </div>
      )}

      <motion.ol variants={item} className="mt-12 grid gap-2 sm:grid-cols-5">
        {WORKFLOW.map((w, i) => (
          <li key={w.key} className="relative rounded-xl border border-white/[0.05] bg-ink-900/50 p-3">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-ink-400">0{i + 1}</span>
              <w.icon className="h-4 w-4 text-violet-300" />
              <span className="text-sm font-medium text-ink-100">{w.label}</span>
            </div>
            <p className="mt-1 text-xs text-ink-400">{w.text}</p>
          </li>
        ))}
      </motion.ol>
    </motion.div>
  )
}
