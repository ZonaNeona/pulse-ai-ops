import clsx from 'clsx'
import type { Kpi } from '@/api/types'
import { Sparkline } from './charts'
import { formatKpi } from './format'
import { Card, Delta } from './kit'
import { toneText } from './tone'

/** KPI tile: label, value, change vs. previous period, sparkline, one-line hint. */
export function Stat({ kpi, className }: { kpi: Kpi; className?: string }) {
  const tone = kpi.value ? kpi.tone : 'neutral'
  return (
    <Card className={clsx('flex min-h-[124px] flex-col', className)}>
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm text-muted">{kpi.label}</span>
        <Delta value={kpi.delta} invert={kpi.invert} />
      </div>
      <div className={clsx('num mt-1.5 text-xl font-semibold tracking-[-0.02em]', toneText[tone])}>{formatKpi(kpi)}</div>
      <div className="mt-auto pt-2">
        {kpi.spark.length > 1 && (
          <Sparkline values={kpi.spark} tone={tone === 'neutral' ? 'accent' : tone} height={24} />
        )}
        <p className="mt-1 truncate text-xs text-muted">{kpi.hint}</p>
      </div>
    </Card>
  )
}
