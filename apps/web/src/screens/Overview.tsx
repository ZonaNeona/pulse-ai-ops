import clsx from 'clsx'
import {
  Activity,
  ArrowRight,
  BookOpen,
  Bot,
  Cable,
  Cpu,
  FileText,
  Sparkles,
  type LucideIcon,
} from 'lucide-react'
import { motion } from 'motion/react'
import type { ActionItem, ModuleId } from '@/api/types'
import { useLastTrace, useOverview } from '@/api/queries'
import { navigate, withQuery } from '@/app/router'
import { PRESETS } from '@/app/presets'
import { Ring } from '@/ui/charts'
import { ms, rubShort, usd } from '@/ui/format'
import { Badge, Button, Card, CardHeader, Dot, ErrorState, PageHeader, Skeleton, type Tone } from '@/ui/kit'
import { Stat } from '@/ui/Stat'

const MODULE_ICON: Record<ModuleId, LucideIcon> = {
  sales: Activity,
  docs: FileText,
  knowledge: BookOpen,
  integrations: Cable,
  agents: Cpu,
}
const SEVERITY: Record<ActionItem['severity'], { tone: Tone; label: string }> = {
  high: { tone: 'danger', label: 'Срочно' },
  medium: { tone: 'warning', label: 'Сегодня' },
  low: { tone: 'neutral', label: 'Когда будет время' },
}

export function Overview() {
  const { data, error, refetch } = useOverview()
  if (error) return <ErrorState error={error} retry={refetch} />
  if (!data) return <OverviewSkeleton />
  const { revenue } = data
  return (
    <>
      <PageHeader
        eyebrow={data.company.today}
        title="Обзор компании"
        description="Что происходит в продажах, документах и учёте прямо сейчас и что сделать в первую очередь."
        actions={
          <Button icon={<Sparkles size={14} />} onClick={() => navigate('/copilot')}>
            Спросить копилота
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5 [&>*:last-child]:col-span-2 md:[&>*:last-child]:col-span-1">
        {data.modules.map((m, i) => {
          const Icon = MODULE_ICON[m.id]
          return (
            <motion.div
              key={m.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04, duration: 0.2 }}
            >
              <Card onClick={() => navigate(m.href)} className="h-full">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm font-medium text-ink">
                    <Icon size={15} className="text-muted" />
                    {m.title}
                  </span>
                  <Dot tone={m.status} pulse={m.status === 'danger'} />
                </div>
                <div className="mt-3 text-md font-semibold tracking-[-0.01em] text-ink">{m.headline}</div>
                <p className="mt-1 line-clamp-2 text-xs text-muted">{m.detail}</p>
              </Card>
            </motion.div>
          )
        })}
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex min-w-0 flex-col gap-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {data.kpis.map((k) => (
              <Stat key={k.key} kpi={k} />
            ))}
          </div>

          <Card padded={false}>
            <div className="flex items-center justify-between px-4 pt-4">
              <CardHeader
                title="Сделать сейчас"
                hint="Собрано из всех модулей и отсортировано по срочности"
                className="mb-0"
              />
              <Badge>{data.actions.length}</Badge>
            </div>
            <ul className="mt-3 divide-y divide-line border-t border-line">
              {data.actions.map((a) => {
                const Icon = MODULE_ICON[a.module]
                const sev = SEVERITY[a.severity]
                return (
                  <li key={a.id} className="flex items-center gap-3 px-4 py-3">
                    <span
                      className={clsx(
                        'grid size-8 shrink-0 place-items-center rounded-md',
                        sev.tone === 'danger'
                          ? 'bg-danger-soft text-danger'
                          : sev.tone === 'warning'
                            ? 'bg-warning-soft text-warning'
                            : 'bg-surface-2 text-muted',
                      )}
                    >
                      <Icon size={15} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-ink">{a.title}</div>
                      <div className="truncate text-xs text-muted">
                        {a.reason}
                        {a.owner && ` · ${a.owner}`}
                      </div>
                    </div>
                    <Badge tone={sev.tone} className="hidden sm:inline-flex">
                      {sev.label}
                    </Badge>
                    <span className="num hidden w-14 text-right text-xs whitespace-nowrap text-faint md:block">
                      {a.age}
                    </span>
                    <Button variant="secondary" size="sm" onClick={() => navigate(a.href)}>
                      {a.action}
                    </Button>
                  </li>
                )
              })}
            </ul>
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader title="План месяца" hint={`Осталось ${revenue.daysLeft} рабочих дней`} />
            <div className="flex items-center gap-4">
              <Ring value={revenue.fact} max={revenue.plan} size={72} stroke={6}>
                {Math.round((revenue.fact / revenue.plan) * 100)}%
              </Ring>
              <dl className="grid flex-1 gap-1.5 text-sm">
                <Row label="Факт" value={rubShort(revenue.fact)} />
                <Row label="План" value={rubShort(revenue.plan)} />
                <Row
                  label="Прогноз"
                  value={rubShort(revenue.forecast)}
                  tone={revenue.forecast < revenue.plan ? 'warning' : 'success'}
                />
              </dl>
            </div>
          </Card>
          <AskCard />
          <LastRunCard />
        </div>
      </div>
    </>
  )
}

function Row({ label, value, tone }: { label: string; value: string; tone?: Tone }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-muted">{label}</dt>
      <dd className={clsx('num font-medium', tone === 'warning' ? 'text-warning' : 'text-ink')}>{value}</dd>
    </div>
  )
}

function AskCard() {
  return (
    <Card>
      <CardHeader
        title="Спросите своими словами"
        hint="Копилот ответит по данным CRM, 1С и регламентам"
        icon={<Bot size={16} />}
      />
      <div className="flex flex-col gap-1.5">
        {PRESETS.slice(0, 3).map((p) => (
          <button
            key={p}
            onClick={() => navigate(withQuery('/copilot', { q: p }))}
            className="group flex items-center justify-between gap-2 rounded-md border border-line px-3 py-2 text-left text-sm text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
          >
            {p}
            <ArrowRight size={14} className="shrink-0 text-faint group-hover:text-accent" />
          </button>
        ))}
      </div>
    </Card>
  )
}

function LastRunCard() {
  const { data, isLoading } = useLastTrace()
  if (isLoading) return <Skeleton className="h-40" />
  if (!data)
    return (
      <Card onClick={() => navigate('/copilot')}>
        <CardHeader
          title="Ход агента"
          hint="Появится после первого вопроса в Копилоте"
          icon={<Cpu size={16} />}
        />
        <p className="text-sm text-muted">
          Под каждым ответом видно, какие инструменты вызывал агент, сколько это заняло и сколько стоило.
        </p>
      </Card>
    )
  const tools = data.steps.filter((s) => s.kind === 'tool').length
  const total = Math.max(data.totalMs, 1)
  return (
    <Card onClick={() => navigate('/under-the-hood')}>
      <CardHeader
        title="Последний ход агента"
        hint={data.startedAgo}
        icon={<Cpu size={16} />}
        action={<Badge tone="accent">{data.engineLabel}</Badge>}
      />
      <p className="line-clamp-2 text-sm text-ink-2">«{data.question}»</p>
      <div className="mt-3 flex flex-col gap-1">
        {data.steps.slice(0, 6).map((s) => (
          <div key={s.id} className="flex items-center gap-2">
            <span className="w-24 truncate text-xs text-muted">{s.lane}</span>
            <div className="relative h-2 flex-1 rounded-full bg-surface-2">
              <span
                className={clsx(
                  'absolute inset-y-0 rounded-full',
                  s.kind === 'tool'
                    ? 'bg-chart-2'
                    : s.kind === 'subagent'
                      ? 'bg-chart-3'
                      : s.kind === 'route'
                        ? 'bg-faint'
                        : 'bg-accent',
                )}
                style={{
                  left: `${Math.min(98, (s.startMs / total) * 100)}%`,
                  width: `${Math.max(2, (s.durMs / total) * 100)}%`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-muted">
        <span>
          {tools} {tools === 1 ? 'инструмент' : tools > 1 && tools < 5 ? 'инструмента' : 'инструментов'} ·{' '}
          {ms(data.totalMs)}
        </span>
        <span className="num text-ink">{data.costUsd ? usd(data.costUsd) : 'бесплатно'}</span>
      </div>
    </Card>
  )
}

function OverviewSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-16 w-80" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-80" />
    </div>
  )
}
