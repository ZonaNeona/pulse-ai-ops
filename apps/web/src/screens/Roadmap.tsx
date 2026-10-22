import clsx from 'clsx'
import { ChevronDown, ExternalLink } from 'lucide-react'
import { Fragment, useMemo, useState } from 'react'
import { Meter } from '@/ui/charts'
import { Badge, Card, PageHeader, Segmented, type Tone } from '@/ui/kit'
import {
  allTasks,
  JOURNAL,
  PROJECT,
  RELEASES,
  STATUS_LABEL,
  type Release,
  type Task,
  type TaskStatus,
} from '@/work/roadmap'

const TONE: Record<TaskStatus, Tone> = {
  planned: 'neutral',
  done: 'info',
  verified: 'accent',
  accepted: 'success',
  waiting: 'warning',
}
const BAR: Record<TaskStatus, string> = {
  planned: 'border border-dashed border-line-strong bg-surface',
  done: 'bg-info',
  verified: 'bg-accent',
  accepted: 'bg-success',
  waiting: 'bg-warning',
}
const DONE: TaskStatus[] = ['done', 'verified', 'accepted']
const WD = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']

const hours = (min: number) => String(Math.round((min / 60) * 10) / 10).replace('.', ',') + ' ч'
const dm = (iso: string) => `${iso.slice(8, 10)}.${iso.slice(5, 7)}`
const span = (t: Task) => (t.to && t.to !== t.from ? `${dm(t.from)}–${dm(t.to)}` : dm(t.from))
const minutes = (tasks: Task[]) => tasks.reduce((s, t) => s + t.min, 0)
const doneMin = (tasks: Task[]) => minutes(tasks.filter((t) => DONE.includes(t.status)))
const releaseTasks = (r: Release) => r.stages.flatMap((s) => s.tasks)

function days(): string[] {
  const out: string[] = []
  const end = new Date(PROJECT.range[1] + 'T00:00:00Z')
  for (let d = new Date(PROJECT.range[0] + 'T00:00:00Z'); d <= end; d = new Date(d.getTime() + 864e5))
    out.push(d.toISOString().slice(0, 10))
  return out
}

type Tab = 'plan' | 'check' | 'journal'

export function Roadmap() {
  const [tab, setTab] = useState<Tab>('plan')
  const tasks = allTasks()
  const pct = Math.round((doneMin(tasks) / minutes(tasks)) * 100)
  return (
    <>
      <PageHeader
        eyebrow={`Как мы работаем · ${PROJECT.client}`}
        title="Дорожная карта"
        description="Так ведётся каждый проект: релизы → этапы → задачи. У задачи — результат простыми словами, оценка, срок и способ проверить самому. Ниже — настоящий ход разработки этого стенда."
        actions={
          <div className="text-right">
            <div className="text-xs text-muted">выполнено</div>
            <div className="num text-2xl font-semibold text-ink">{pct}%</div>
            <div className="num text-xs text-muted">
              {hours(doneMin(tasks))} из {hours(minutes(tasks))}
            </div>
          </div>
        }
      />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {RELEASES.map((r) => {
          const ts = releaseTasks(r)
          const done = ts.filter((t) => DONE.includes(t.status)).length
          const state = done === ts.length ? 'Готов' : done ? 'В работе' : 'Не начат'
          return (
            <Card key={r.code}>
              <div className="flex items-start justify-between gap-2">
                <span className="mono text-xs text-faint">{r.code}</span>
                <Badge tone={done === ts.length ? 'success' : done ? 'accent' : 'neutral'}>{state}</Badge>
              </div>
              <div className="mt-1 text-md font-semibold text-ink">{r.title}</div>
              <div className="mt-1 text-xs text-muted">{r.milestone}</div>
              <Meter value={doneMin(ts)} max={minutes(ts)} className="mt-3" />
              <div className="num mt-2 flex justify-between text-xs text-muted">
                <span>
                  {hours(doneMin(ts))} из {hours(minutes(ts))}
                </span>
                <span>
                  {done} из {ts.length} задач
                </span>
              </div>
            </Card>
          )
        })}
      </div>

      <Segmented
        className="mt-6"
        value={tab}
        onChange={setTab}
        options={[
          { id: 'plan' as Tab, label: 'План' },
          { id: 'check' as Tab, label: 'Проверка и приёмка' },
          { id: 'journal' as Tab, label: 'Журнал работ' },
        ]}
      />
      <div className="mt-4">
        {tab === 'plan' && <Plan />}
        {tab === 'check' && <Checks />}
        {tab === 'journal' && <Journal />}
      </div>
    </>
  )
}

function Legend() {
  return (
    <div className="mb-3 flex flex-wrap gap-3 text-xs text-muted">
      {(['accepted', 'verified', 'done', 'waiting', 'planned'] as TaskStatus[]).map((s) => (
        <span key={s} className="inline-flex items-center gap-1.5">
          <span className={clsx('h-2.5 w-4 rounded-[3px]', BAR[s])} />
          {STATUS_LABEL[s]}
        </span>
      ))}
    </div>
  )
}

function Plan() {
  const cols = useMemo(days, [])
  const at = Object.fromEntries(cols.map((d, i) => [d, i]))
  const [closed, setClosed] = useState<Set<string>>(new Set())
  const toggle = (key: string) =>
    setClosed((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  const grid = `minmax(260px,1fr) 84px 64px 150px repeat(${cols.length}, 30px)`
  const bar = (from: string, to: string | undefined, status: TaskStatus) => {
    const a = at[from] ?? 0
    const b = at[to ?? from] ?? a
    return (
      <div
        className="relative grid h-full"
        style={{ gridColumn: `5 / span ${cols.length}`, gridTemplateColumns: `repeat(${cols.length}, 30px)` }}
      >
        <span
          className={clsx('my-auto h-2.5 rounded-[3px]', BAR[status])}
          style={{ gridColumn: `${a + 1} / ${b + 2}` }}
        />
      </div>
    )
  }
  return (
    <Card padded={false}>
      <div className="px-4 pt-4">
        <Legend />
      </div>
      <div className="overflow-x-auto">
        <div className="min-w-[900px] text-sm">
          <div
            className="grid border-y border-line bg-surface-2/60 text-xs text-muted"
            style={{ gridTemplateColumns: grid }}
          >
            <div className="px-4 py-2">Релиз · этап · задача</div>
            <div className="py-2">Сроки</div>
            <div className="py-2 text-right">Оценка</div>
            <div className="py-2 pl-4">Статус</div>
            {cols.map((d) => {
              const wd = new Date(d + 'T00:00:00Z').getUTCDay()
              return (
                <div
                  key={d}
                  className={clsx(
                    'py-1 text-center leading-tight',
                    (wd === 0 || wd === 6) && 'bg-surface-3/60',
                  )}
                >
                  <div className="num text-ink-2">{d.slice(8, 10)}</div>
                  <div className="text-[10px]">{WD[wd]}</div>
                </div>
              )
            })}
          </div>
          {RELEASES.map((r) => {
            const ts = releaseTasks(r)
            const from = ts.map((t) => t.from).sort()[0]
            const ends = ts.map((t) => t.to ?? t.from).sort()
            const to = ends[ends.length - 1]
            return (
              <Fragment key={r.code}>
                <button
                  onClick={() => toggle(r.code)}
                  className="grid w-full cursor-pointer items-center border-b border-line bg-accent-soft/40 text-left"
                  style={{ gridTemplateColumns: grid }}
                >
                  <div className="flex items-center gap-1.5 px-4 py-2.5">
                    <ChevronDown
                      size={14}
                      className={clsx('text-muted transition-transform', closed.has(r.code) && '-rotate-90')}
                    />
                    <span className="mono text-xs text-faint">{r.code}</span>
                    <span className="font-semibold text-ink">{r.title}</span>
                  </div>
                  <div className="num text-xs text-muted">
                    {from === to ? dm(from) : `${dm(from)}–${dm(to ?? from)}`}
                  </div>
                  <div className="num text-right text-xs text-ink">{hours(minutes(ts))}</div>
                  <div className="pl-4 text-xs text-muted">
                    {Math.round((doneMin(ts) / minutes(ts)) * 100)}%
                  </div>
                  {bar(from, to, ts.every((t) => DONE.includes(t.status)) ? 'accepted' : 'verified')}
                </button>
                {!closed.has(r.code) &&
                  r.stages.map((s) => (
                    <Fragment key={s.title}>
                      <div
                        className="grid items-center border-b border-line bg-surface-2/30"
                        style={{ gridTemplateColumns: grid }}
                      >
                        <div className="py-2 pr-2 pl-9">
                          <div className="font-medium text-ink">{s.title}</div>
                          <div className="text-xs text-muted">{s.goal}</div>
                        </div>
                        <div />
                        <div className="num text-right text-xs text-muted">{hours(minutes(s.tasks))}</div>
                        <div />
                      </div>
                      {s.tasks.map((t) => (
                        <div
                          key={t.code}
                          className="grid items-center border-b border-line hover:bg-surface-2/40"
                          style={{ gridTemplateColumns: grid }}
                        >
                          <div className="flex gap-2 py-2 pr-2 pl-9">
                            <span
                              className={clsx(
                                'mono w-16 shrink-0 pt-px text-[11px]',
                                t.control ? 'text-warning' : 'text-faint',
                              )}
                            >
                              {t.code}
                            </span>
                            <div className="min-w-0">
                              <div className="text-ink">
                                {t.title}
                                {t.control && (
                                  <span className="ml-1.5 rounded-sm bg-warning-soft px-1 text-[10px] font-semibold text-warning">
                                    КОНТРОЛЬ
                                  </span>
                                )}
                              </div>
                              <div className="text-xs text-muted">{t.outcome}</div>
                            </div>
                          </div>
                          <div className="num text-xs text-muted">{span(t)}</div>
                          <div className="num text-right text-xs text-ink">{t.min} мин</div>
                          <div className="pl-4">
                            <Badge tone={TONE[t.status]}>{STATUS_LABEL[t.status]}</Badge>
                          </div>
                          {bar(t.from, t.to, t.status)}
                        </div>
                      ))}
                    </Fragment>
                  ))}
              </Fragment>
            )
          })}
        </div>
      </div>
    </Card>
  )
}

function Checks() {
  const groups: TaskStatus[] = ['waiting', 'done', 'verified', 'accepted', 'planned']
  const tasks = allTasks()
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {groups.map((status) => {
        const items = tasks.filter((t) => t.status === status)
        if (!items.length) return null
        return (
          <Card key={status}>
            <div className="mb-3 flex items-center justify-between">
              <Badge tone={TONE[status]} dot>
                {STATUS_LABEL[status]}
              </Badge>
              <span className="text-xs text-muted">{items.length}</span>
            </div>
            <ul className="flex flex-col divide-y divide-line">
              {items.map((t) => (
                <li key={t.code} className="flex items-start gap-3 py-2.5 text-sm">
                  <span className="mono w-16 shrink-0 pt-px text-[11px] text-faint">{t.code}</span>
                  <div className="min-w-0 flex-1">
                    <div className="text-ink">{t.title}</div>
                    <div className="text-xs text-muted">{t.outcome}</div>
                  </div>
                  {t.check && (
                    <a
                      href={t.check.href}
                      target={t.check.href.startsWith('http') ? '_blank' : undefined}
                      rel="noreferrer"
                      className="inline-flex shrink-0 items-center gap-1 text-xs text-accent hover:underline"
                    >
                      {t.check.label}
                      {t.check.href.startsWith('http') && <ExternalLink size={11} />}
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        )
      })}
    </div>
  )
}

function Journal() {
  return (
    <Card>
      <ol className="relative flex flex-col gap-5 border-l border-line pl-5">
        {[...JOURNAL].reverse().map((e) => (
          <li key={e.title} className="relative">
            <span className="absolute top-1.5 -left-[25px] size-2.5 rounded-full border-2 border-surface bg-accent" />
            <div className="num text-xs text-muted">{dm(e.date)}</div>
            <div className="font-medium text-ink">{e.title}</div>
            <p className="mt-0.5 text-sm text-ink-2">{e.text}</p>
          </li>
        ))}
      </ol>
    </Card>
  )
}
