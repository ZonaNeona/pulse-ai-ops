// Small SVG charts drawn with theme variables, so light and dark switch without extra logic.
import clsx from 'clsx'
import { useId, useState, type ReactNode } from 'react'
import type { Tone } from './tone'

const toneVar: Record<Tone, string> = {
  neutral: 'var(--chart-5)',
  accent: 'var(--accent)',
  danger: 'var(--danger)',
  warning: 'var(--warning)',
  success: 'var(--success)',
  info: 'var(--info)',
}

export function Sparkline({
  values,
  tone = 'accent',
  height = 28,
  className,
}: {
  values: number[]
  tone?: Tone
  height?: number
  className?: string
}) {
  const id = useId()
  const w = 100
  const max = Math.max(1, ...values)
  const min = Math.min(0, ...values)
  const span = max - min || 1
  const pts = values.map((v, i) => [
    values.length === 1 ? w : (i / (values.length - 1)) * w,
    height - 2 - ((v - min) / span) * (height - 4),
  ])
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')
  const color = toneVar[tone]
  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      className={clsx('block w-full', className)}
      style={{ height }}
      aria-hidden
    >
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity=".2" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${line} L${w},${height} L0,${height} Z`} fill={`url(#${id})`} />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}

export type BarSeries = { key: string; label: string; color: string }
/** `label` sits under the bar, `title` (falls back to label) is shown in the hover read-out. */
export type BarPoint = { key: string; label: string; title?: string; muted?: boolean; values: Record<string, number> }

/** Stacked vertical bars with hover read-out and a legend. */
export function StackedBars({
  points,
  series,
  height = 168,
  summary,
}: {
  points: BarPoint[]
  series: BarSeries[]
  height?: number
  summary?: ReactNode
}) {
  const [hover, setHover] = useState<number | null>(null)
  const totals = points.map((p) => series.reduce((s, x) => s + (p.values[x.key] ?? 0), 0))
  const max = Math.max(1, ...totals)
  const n = points.length
  const labelEvery = n <= 10 ? 1 : n <= 20 ? 2 : 5
  const active = hover !== null ? points[hover] : null
  return (
    <div>
      <div className="mb-3 flex h-9 items-end justify-between gap-3 text-sm">
        {active ? (
          <div>
            <div className="font-medium text-ink">{active.title ?? active.label}</div>
            <div className="num text-muted">
              {series.map((s) => `${s.label.toLowerCase()} ${active.values[s.key] ?? 0}`).join(' · ')}
            </div>
          </div>
        ) : (
          <div className="text-muted">{summary}</div>
        )}
        <div className="flex flex-wrap justify-end gap-x-3 gap-y-1 text-xs text-muted">
          {series.map((s) => (
            <span key={s.key} className="inline-flex items-center gap-1.5">
              <span className="size-2 rounded-[2px]" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
      </div>
      <div className="relative" style={{ height }} onMouseLeave={() => setHover(null)}>
        {[1, 0.5].map((t) => (
          <div
            key={t}
            className="absolute inset-x-0 border-t border-dashed border-line"
            style={{ top: `${(1 - t) * 100}%` }}
          >
            <span className="num absolute -top-2 right-0 bg-surface pl-1 text-[10px] text-faint">
              {Math.round(max * t)}
            </span>
          </div>
        ))}
        <div className="absolute inset-0 flex items-stretch gap-[3px] border-b border-line-strong pr-6">
          {points.map((p, i) => {
            const parts = series.filter((s) => (p.values[s.key] ?? 0) > 0)
            return (
              <div
                key={p.key}
                onMouseEnter={() => setHover(i)}
                className="flex flex-1 flex-col-reverse items-center gap-px rounded-sm"
              >
                {parts.map((s, j) => (
                  <span
                    key={s.key}
                    className={clsx(
                      'w-full max-w-[18px] transition-opacity duration-200',
                      j === parts.length - 1 && 'rounded-t-[3px]',
                    )}
                    style={{
                      height: `${((p.values[s.key] ?? 0) / max) * 96}%`,
                      background: s.color,
                      opacity: hover === null || hover === i ? (p.muted ? 0.55 : 1) : 0.35,
                    }}
                  />
                ))}
              </div>
            )
          })}
        </div>
      </div>
      <div className="relative mt-1.5 mr-6 h-4">
        {points.map(
          (p, i) =>
            (i % labelEvery === 0 || i === n - 1) && (
              <span
                key={p.key}
                className={clsx('num absolute -translate-x-1/2 text-[10px]', p.muted ? 'text-faint' : 'text-muted')}
                style={{ left: `${((i + 0.5) / n) * 100}%` }}
              >
                {p.label}
              </span>
            ),
        )}
      </div>
    </div>
  )
}

export function Ring({
  value,
  max,
  size = 44,
  stroke = 4,
  tone = 'accent',
  children,
}: {
  value: number
  max: number
  size?: number
  stroke?: number
  tone?: Tone
  children?: ReactNode
}) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const pct = max ? Math.min(1, value / max) : 0
  return (
    <span className="relative inline-grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={toneVar[tone]}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          style={{ transition: 'stroke-dashoffset .8s var(--ease-out)' }}
        />
      </svg>
      <span className="num absolute text-xs font-semibold text-ink">{children}</span>
    </span>
  )
}

export function Meter({
  value,
  max,
  tone = 'accent',
  className,
}: {
  value: number
  max: number
  tone?: Tone
  className?: string
}) {
  const pct = max ? Math.min(100, (value / max) * 100) : 0
  return (
    <div className={clsx('h-1.5 overflow-hidden rounded-full bg-surface-3', className)}>
      <div
        className="h-full rounded-full transition-[width] duration-700 ease-out"
        style={{ width: `${pct}%`, background: toneVar[tone] }}
      />
    </div>
  )
}
