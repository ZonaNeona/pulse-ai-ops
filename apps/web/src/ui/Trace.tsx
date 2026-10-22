import clsx from 'clsx'
import type { TraceRun, TraceStep } from '@/api/types'
import { ms, usd } from './format'

const KIND: Record<TraceStep['kind'], { label: string; bar: string; chip: string }> = {
  route: { label: 'Маршрут', bar: 'bg-faint', chip: 'bg-surface-2 text-muted' },
  llm: { label: 'Модель', bar: 'bg-accent', chip: 'bg-accent-soft text-accent' },
  tool: { label: 'Инструмент', bar: 'bg-chart-2', chip: 'bg-success-soft text-success' },
  subagent: { label: 'Подагент', bar: 'bg-chart-3', chip: 'bg-warning-soft text-warning' },
  graph: { label: 'Граф', bar: 'bg-chart-4', chip: 'bg-danger-soft text-danger' },
}

/** Timeline of one agent run: lanes (main agent, subagents) × time, every step with its duration. */
export function TraceTimeline({ run, compact }: { run: TraceRun; compact?: boolean }) {
  const lanes = [...new Set(run.steps.map((s) => s.lane))]
  const kinds = new Set(run.steps.map((s) => s.kind))
  const total = Math.max(run.totalMs, 1)
  const ticks = [0, 0.25, 0.5, 0.75, 1]
  return (
    <div>
      <div className="flex flex-wrap gap-3 text-xs text-muted">
        {Object.entries(KIND)
          .filter(([k]) => kinds.has(k as TraceStep['kind']))
          .map(([k, v]) => (
            <span key={k} className="inline-flex items-center gap-1.5">
              <span className={clsx('size-2 rounded-[2px]', v.bar)} />
              {v.label}
            </span>
          ))}
      </div>
      <div className="mt-3 flex flex-col gap-1.5">
        <div className="relative ml-28 h-4">
          {ticks.map((t) => (
            <span
              key={t}
              className="num absolute -translate-x-1/2 text-[10px] text-faint"
              style={{ left: `${t * 100}%` }}
            >
              {ms(total * t)}
            </span>
          ))}
        </div>
        {lanes.map((lane) => (
          <div key={lane} className="flex items-center gap-2">
            <span className="w-26 shrink-0 truncate text-xs text-muted">{lane}</span>
            <div className="relative h-7 flex-1 rounded-md bg-surface-2/70">
              {run.steps
                .filter((s) => s.lane === lane)
                .map((s) => (
                  <span
                    key={s.id}
                    title={`${s.label} · ${ms(s.durMs)}`}
                    className={clsx(
                      'absolute top-1 bottom-1 flex items-center overflow-hidden rounded-sm px-1.5 text-[10.5px] font-medium whitespace-nowrap text-white/95',
                      KIND[s.kind].bar,
                      s.kind === 'subagent' && 'opacity-35',
                    )}
                    style={{
                      left: `${Math.min(98.5, (s.startMs / total) * 100)}%`,
                      width: `${Math.max(1.5, (s.durMs / total) * 100)}%`,
                    }}
                  >
                    {s.kind !== 'subagent' && s.name}
                  </span>
                ))}
            </div>
          </div>
        ))}
      </div>
      {!compact && (
        <ol className="mt-4 divide-y divide-line rounded-md border border-line">
          {run.steps.map((s) => (
            <li key={s.id} className="flex items-center gap-3 px-3 py-2 text-sm">
              <span
                className={clsx(
                  'w-24 shrink-0 rounded-sm px-1.5 py-0.5 text-center text-[11px] font-medium',
                  KIND[s.kind].chip,
                )}
              >
                {KIND[s.kind].label}
              </span>
              <span className="mono min-w-0 flex-1 truncate text-xs text-ink">{s.label}</span>
              <span className="hidden truncate text-xs text-muted md:block md:w-48">{s.detail}</span>
              <span className="num w-14 text-right text-xs text-muted">{ms(s.durMs)}</span>
              <span className="num w-16 text-right text-xs text-faint">
                {s.costUsd ? usd(s.costUsd) : ''}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
