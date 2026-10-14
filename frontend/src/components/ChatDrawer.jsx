import { AnimatePresence, motion } from 'framer-motion'
import { MessageSquareText, Send, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useGemma } from '../hooks/useGemma'
import { useStatus } from '../hooks/useStatus'
import { api } from '../services/api'
import { renderMarkdown } from '../utils/format'
import { Badge, Button, Drawer, InlineNotice } from './ui'

const SUGGESTIONS = [
  'What happens if the database is down?',
  'Which routes call the external API?',
  'Where are environment variables read?',
  'Explain the order placement flow.',
]

/** Conversational assistant grounded in the analysed repository (Gemma, consent-gated). */
export default function ChatDrawer({ open, onClose, project }) {
  const { runAI } = useGemma()
  const status = useStatus()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)

  useEffect(() => setMessages([]), [project.id])
  useEffect(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), [messages, busy])

  const ask = async (q) => {
    const question = (q ?? input).trim()
    if (!question || busy) return
    setInput('')
    const history = messages.filter((m) => !m.error).map((m) => ({ role: m.role, content: m.content }))
    setMessages((m) => [...m, { role: 'user', content: question }])
    setBusy(true)
    try {
      const res = await runAI((body) => api.chat(project.id, { ...body, question, history }), 'Repository Q&A')
      setMessages((m) => [...m, { role: 'assistant', content: res.result.answer, meta: res.meta, cited: res.result.cited_components, confidence: res.result.confidence }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', content: e.message, error: true }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <Drawer open={open} onClose={onClose} title="Ask DevDNA" subtitle={`${project.name} · answers grounded in analysis evidence`} icon={MessageSquareText} width="max-w-lg">
      <div className="flex h-full flex-col">
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {status?.ai && !status.ai.configured && (
            <InlineNotice tone="violet" icon={Sparkles}>
              The assistant uses Gemma, which is not configured. <Link className="underline" to="/settings" onClick={onClose}>Enable it in Settings</Link>.
            </InlineNotice>
          )}
          {messages.length === 0 && (
            <div className="space-y-2">
              <p className="text-sm text-ink-300">Ask about routes, dependencies or failure behaviour. Relevant components are retrieved from the graph and shown to you before anything is sent.</p>
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => ask(s)} className="block w-full rounded-lg border border-white/[0.06] bg-ink-900/50 px-3 py-2 text-left text-sm text-ink-200 hover:border-violet-400/30">
                  {s}
                </button>
              ))}
            </div>
          )}
          <AnimatePresence initial={false}>
            {messages.map((m, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={m.role === 'user' ? 'flex justify-end' : ''}>
                {m.role === 'user' ? (
                  <div className="max-w-[85%] rounded-xl rounded-br-sm bg-violet-500/20 px-3 py-2 text-sm text-ink-100">{m.content}</div>
                ) : (
                  <div className={`rounded-xl rounded-bl-sm border px-3 py-2 text-sm ${m.error ? 'border-rose-500/25 bg-rose-500/5 text-rose-200' : 'border-white/[0.06] bg-ink-900/70 text-ink-200'}`}>
                    {m.error ? m.content : <div className="prose-dna" dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />}
                    {m.cited?.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {m.cited.slice(0, 8).map((c) => (
                          <Link key={c} to={`/architecture?focus=${encodeURIComponent(c)}`} onClick={onClose}>
                            <Badge className="border-cyan-400/20 bg-cyan-400/5 font-mono text-cyan-200 hover:bg-cyan-400/15">{c.replace(/^\w+:/, '')}</Badge>
                          </Link>
                        ))}
                      </div>
                    )}
                    {m.meta && <div className="mt-2 text-[10px] text-ink-400">{m.meta.model} · confidence {m.confidence}</div>}
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
          {busy && (
            <div className="flex items-center gap-1.5 px-1 text-xs text-ink-400">
              {[0, 1, 2].map((i) => (
                <motion.span key={i} className="h-1.5 w-1.5 rounded-full bg-violet-300" animate={{ opacity: [0.2, 1, 0.2] }} transition={{ repeat: Infinity, duration: 1, delay: i * 0.15 }} />
              ))}
            </div>
          )}
          <div ref={endRef} />
        </div>
        <form
          className="flex gap-2 border-t border-white/[0.06] p-3"
          onSubmit={(e) => {
            e.preventDefault()
            ask()
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            maxLength={2000}
            placeholder="Ask about this repository…"
            aria-label="Question"
            className="flex-1 rounded-lg border border-ink-600 bg-ink-900 px-3 py-2 text-sm text-ink-100 outline-none focus:border-violet-400"
          />
          <Button type="submit" variant="primary" icon={Send} loading={busy} disabled={!input.trim()}>
            <span className="sr-only">Send</span>
          </Button>
        </form>
      </div>
    </Drawer>
  )
}
