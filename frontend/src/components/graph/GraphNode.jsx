import { Handle, Position } from '@xyflow/react'
import { memo } from 'react'
import { NODE_TYPES } from '../../utils/constants'

/** A single component in the architecture graph. Dimming/highlight state is passed in `data`. */
function GraphNode({ data, selected }) {
  const t = NODE_TYPES[data.type] || NODE_TYPES.function
  const Icon = t.icon
  const tone =
    data.state === 'impact-definite'
      ? 'border-rose-400/70 bg-rose-500/10 shadow-[0_0_24px_-6px_rgba(244,63,94,0.7)]'
      : data.state === 'impact-possible'
        ? 'border-amber-300/60 bg-amber-400/10'
        : data.state === 'source'
          ? 'border-rose-300 bg-rose-500/20 shadow-[0_0_30px_-4px_rgba(244,63,94,0.9)]'
          : data.state === 'upstream'
            ? 'border-violet-400/60 bg-violet-500/10'
            : data.state === 'downstream'
              ? 'border-cyan-400/60 bg-cyan-400/10'
              : data.state === 'match'
                ? 'border-cyan-300 bg-cyan-400/10'
                : 'border-white/10 bg-ink-800/95'
  return (
    <div
      className={`flex h-[46px] w-[210px] items-center gap-2 rounded-lg border px-2.5 transition-all duration-200 ${tone} ${selected ? 'ring-2 ring-violet-400' : ''} ${data.dimmed ? 'opacity-25' : 'opacity-100'}`}
      title={data.id}
    >
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-ink-500" />
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md" style={{ background: `${t.color}1f`, color: t.color }}>
        <Icon className="h-3.5 w-3.5" />
      </span>
      <div className="min-w-0 leading-tight">
        <div className="truncate text-[12px] font-medium text-ink-100">{data.label}</div>
        <div className="truncate text-[10px] text-ink-400">{data.sub}</div>
      </div>
      {data.criticality > 0 && (
        <span className="ml-auto shrink-0 rounded bg-ink-900/80 px-1 font-mono text-[9px] text-ink-300" title="Criticality score">
          {Math.round(data.criticality)}
        </span>
      )}
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-ink-500" />
    </div>
  )
}

export default memo(GraphNode)
