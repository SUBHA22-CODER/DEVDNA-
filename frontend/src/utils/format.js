export function timeAgo(iso) {
  if (!iso) return '—'
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return new Date(iso).toLocaleDateString()
}

export function pct(v) {
  return v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`
}

export function bytes(n) {
  if (!n && n !== 0) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

/** Deterministic suggestion for the next test (mirrors the backend report logic). */
export function nextTestSuggestion(comparison) {
  const rows = comparison?.rows || []
  const mismatch = rows.find((r) => r.verdict === 'mismatch')
  if (mismatch) {
    return `Investigate ${mismatch.nodeid}: predicted "${mismatch.prediction}" but observed "${mismatch.observed}". Add a focused test that asserts the behaviour along ${(mismatch.path || []).join(' → ') || 'its call path'}.`
  }
  const uncertain = rows.find((r) => (r.verdict || '').startsWith('uncertain'))
  if (uncertain) return `Add an assertion that pins down the handled-error behaviour of ${uncertain.nodeid} (currently uncertain).`
  return 'Run the same scenario against another dependency, or add a test for an untested route.'
}

/** Tiny, safe Markdown renderer for AI answers (escapes HTML first). */
export function renderMarkdown(src = '') {
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const inline = (s) =>
    esc(s)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>')
  const lines = src.split('\n')
  const out = []
  let list = null
  let code = null
  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      if (code) {
        out.push(`<pre><code>${esc(code.join('\n'))}</code></pre>`)
        code = null
      } else code = []
      continue
    }
    if (code) {
      code.push(line)
      continue
    }
    const bullet = line.match(/^\s*[-*]\s+(.*)/)
    const num = line.match(/^\s*\d+\.\s+(.*)/)
    if (bullet || num) {
      const tag = bullet ? 'ul' : 'ol'
      if (list !== tag) {
        if (list) out.push(`</${list}>`)
        out.push(`<${tag}>`)
        list = tag
      }
      out.push(`<li>${inline((bullet || num)[1])}</li>`)
      continue
    }
    if (list) {
      out.push(`</${list}>`)
      list = null
    }
    const h = line.match(/^(#{1,3})\s+(.*)/)
    if (h) out.push(`<h3>${inline(h[2])}</h3>`)
    else if (line.trim()) out.push(`<p>${inline(line)}</p>`)
  }
  if (list) out.push(`</${list}>`)
  if (code) out.push(`<pre><code>${esc(code.join('\n'))}</code></pre>`)
  return out.join('')
}
