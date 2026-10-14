import { describe, expect, it } from 'vitest'
import { nextTestSuggestion, pct, renderMarkdown } from '../utils/format'
import { filterGraph, layout, neighbourhood, shortId } from '../utils/graph'

const edges = [
  { id: '1', source: 'route:GET /a', target: 'func:a', type: 'handled_by' },
  { id: '2', source: 'func:a', target: 'func:db', type: 'calls' },
  { id: '3', source: 'func:db', target: 'database:sqlite', type: 'uses_database' },
  { id: '4', source: 'module:m', target: 'func:a', type: 'contains' },
]
const components = [
  { id: 'route:GET /a', type: 'route', name: 'GET /a' },
  { id: 'func:a', type: 'function', name: 'a' },
  { id: 'func:db', type: 'function', name: 'get_db', file: 'app/db.py' },
  { id: 'database:sqlite', type: 'database', name: 'sqlite database' },
  { id: 'module:m', type: 'module', name: 'm' },
]

describe('graph utils', () => {
  it('computes upstream and downstream over propagating edges only', () => {
    const { upstream, downstream } = neighbourhood(edges, 'func:db')
    expect([...upstream].sort()).toEqual(['func:a', 'route:GET /a'])
    expect([...downstream]).toEqual(['database:sqlite'])
    // `contains` does not propagate failures
    expect(neighbourhood(edges, 'func:a').upstream.has('module:m')).toBe(false)
  })

  it('filters by type and finds search matches', () => {
    const g = filterGraph(components, edges, { types: new Set(['function', 'database']), edgeTypes: new Set(['calls', 'uses_database']), query: 'db.py' })
    expect(g.nodes.map((n) => n.id)).toEqual(['func:a', 'func:db', 'database:sqlite'])
    expect(g.edges.map((e) => e.id)).toEqual(['2', '3'])
    expect([...g.matches]).toEqual(['func:db'])
  })

  it('lays out dependents left of dependencies', () => {
    const pos = layout(components.slice(0, 4), edges.slice(0, 3))
    expect(pos['route:GET /a'].x).toBeLessThan(pos['database:sqlite'].x)
  })

  it('shortens ids', () => {
    expect(shortId('func:app.db.get')).toBe('app.db.get')
    expect(shortId('route:GET /x')).toBe('route:GET /x')
  })
})

describe('format utils', () => {
  it('formats percentages and missing values', () => {
    expect(pct(0.917)).toBe('92%')
    expect(pct(null)).toBe('—')
  })

  it('suggests investigating the first mismatch', () => {
    const s = nextTestSuggestion({ rows: [{ verdict: 'match' }, { verdict: 'mismatch', nodeid: 't::x', prediction: 'fail', observed: 'passed', path: ['a', 'b'] }] })
    expect(s).toContain('t::x')
    expect(s).toContain('a → b')
  })

  it('renders markdown safely', () => {
    const html = renderMarkdown('Hello **world** `code`\n- item <script>')
    expect(html).toContain('<strong>world</strong>')
    expect(html).toContain('<code>code</code>')
    expect(html).toContain('<li>item &lt;script&gt;</li>')
    expect(html).not.toContain('<script>')
  })
})
