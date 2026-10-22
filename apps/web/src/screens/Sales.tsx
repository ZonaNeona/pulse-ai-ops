import clsx from 'clsx'
import { ArrowDownLeft, ArrowUpRight, PhoneMissed, Play, Sparkles } from 'lucide-react'
import { useState } from 'react'
import type { Call, Manager, Signal } from '@/api/types'
import { useCallReview, useCalls, useDeals, useFunnels, usePulse, useTeam } from '@/api/queries'
import { navigate, useRoute, withQuery } from '@/app/router'
import { Meter, Ring, Sparkline, StackedBars } from '@/ui/charts'
import { count, duration, num, rubShort } from '@/ui/format'
import {
  Avatar,
  Badge,
  Button,
  Card,
  CardHeader,
  Dot,
  Empty,
  Field,
  PageHeader,
  Segmented,
  Skeleton,
  type Tone,
} from '@/ui/kit'
import { Sheet } from '@/ui/Sheet'
import { Stat } from '@/ui/Stat'
import { useToast } from '@/ui/Toast'

const TABS = [
  { id: '/sales', label: 'Пульс' },
  { id: '/sales/team', label: 'Команда' },
  { id: '/sales/deals', label: 'Сделки' },
  { id: '/sales/calls', label: 'Звонки' },
] as const
type TabId = (typeof TABS)[number]['id']

export function Sales() {
  const { path } = useRoute()
  const tab = (TABS.find((t) => t.id === path)?.id ?? '/sales') as TabId
  return (
    <>
      <PageHeader
        eyebrow="Модуль · Продажи"
        title="Отдел продаж"
        description="Данные из Битрикс24: звонки, сделки, задачи. Сигналы считаются правилами, оценка звонков — моделью с проверкой цитат."
        actions={<Segmented options={[...TABS]} value={tab} onChange={(id) => navigate(id)} />}
      />
      {tab === '/sales' && <PulseTab />}
      {tab === '/sales/team' && <TeamTab />}
      {tab === '/sales/deals' && <DealsTab />}
      {tab === '/sales/calls' && <CallsTab />}
    </>
  )
}

const SEVERITY_TONE: Record<Signal['severity'], Tone> = { high: 'danger', medium: 'warning', low: 'neutral' }

function PulseTab() {
  const { data } = usePulse()
  if (!data) return <Skeleton className="h-96" />
  const total = data.series.reduce((s, p) => s + p.out + p.in + p.missed, 0)
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {data.kpis.map((k) => (
          <Stat key={k.key} kpi={k} />
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card>
          <CardHeader title="Звонки за 14 дней" hint="По данным телефонии Битрикс24" />
          <StackedBars
            summary={`${num(total)} звонков за период`}
            series={[
              { key: 'out', label: 'Исходящие', color: 'var(--chart-1)' },
              { key: 'in', label: 'Входящие', color: 'var(--chart-2)' },
              { key: 'missed', label: 'Пропущенные', color: 'var(--chart-4)' },
            ]}
            points={data.series.map((p) => ({
              key: p.key,
              label: p.label.split(' ')[0],
              title: p.label,
              muted: p.weekend,
              values: { out: p.out, in: p.in, missed: p.missed },
            }))}
          />
        </Card>
        <Card padded={false}>
          <div className="px-4 pt-4">
            <CardHeader title="Сигналы" hint={`${count(data.signals.length, ['правило сработало', 'правила сработали', 'правил сработало'])}`} />
          </div>
          <ul className="divide-y divide-line border-t border-line">
            {data.signals.map((s) => (
              <li key={s.id} className="px-4 py-3">
                <div className="flex items-start gap-2.5">
                  <Dot tone={SEVERITY_TONE[s.severity]} className="mt-1.5" pulse={s.severity === 'high'} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2 text-xs text-muted">
                      <span>{s.ruleLabel}</span>
                      <span className="shrink-0">{s.manager}</span>
                    </div>
                    <div className="mt-0.5 text-sm font-medium text-ink">{s.title}</div>
                    <div className="mt-0.5 text-xs text-muted">{s.reason}</div>
                    <Button size="sm" variant="secondary" className="mt-2" onClick={() => navigate(s.href ?? '/sales')}>
                      {s.action}
                    </Button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}

function TeamTab() {
  const { data } = useTeam()
  const [open, setOpen] = useState<Manager | null>(null)
  if (!data) return <Skeleton className="h-96" />
  return (
    <>
      <Card padded={false} className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="border-b border-line bg-surface-2/60 text-left text-xs text-muted">
              <tr>
                <th className="px-4 py-2.5 font-medium">Менеджер</th>
                <th className="px-3 py-2.5 font-medium">Звонки / норма к этому часу</th>
                <th className="px-3 py-2.5 font-medium">Разговор, мин</th>
                <th className="px-3 py-2.5 font-medium">Оценка</th>
                <th className="px-3 py-2.5 font-medium">Просрочки</th>
                <th className="px-3 py-2.5 text-right font-medium">Воронка</th>
                <th className="px-4 py-2.5 font-medium">10 дней</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.map((m) => {
                const pct = m.callsToday / m.callsNorm
                return (
                  <tr
                    key={m.id}
                    onClick={() => setOpen(m)}
                    className="cursor-pointer transition-colors hover:bg-surface-2/60"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <Avatar name={m.name} seed={m.id} />
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 font-medium text-ink">
                            {m.name}
                            <Dot tone={m.status} />
                          </div>
                          <div className="truncate text-xs text-muted">{m.note}</div>
                        </div>
                      </div>
                    </td>
                    <td className="w-40 px-3 py-3">
                      <div className="num flex justify-between text-xs">
                        <span className="text-ink">{m.callsToday}</span>
                        <span className="text-muted">{m.callsNorm}</span>
                      </div>
                      <Meter
                        value={m.callsToday}
                        max={m.callsNorm}
                        tone={pct >= 0.9 ? 'success' : pct >= 0.6 ? 'warning' : 'danger'}
                        className="mt-1"
                      />
                    </td>
                    <td className="num px-3 py-3 text-ink">{m.talkMin}</td>
                    <td className="px-3 py-3">
                      <Ring value={m.quality} max={100} size={32} stroke={3} tone={m.quality >= 75 ? 'success' : m.quality >= 60 ? 'warning' : 'danger'}>
                        {m.quality}
                      </Ring>
                    </td>
                    <td className="px-3 py-3">
                      {m.overdue ? <Badge tone={m.overdue > 3 ? 'danger' : 'warning'}>{m.overdue}</Badge> : <span className="text-faint">—</span>}
                    </td>
                    <td className="num px-3 py-3 text-right text-ink">{rubShort(m.pipeline)}</td>
                    <td className="w-32 px-4 py-3">
                      <Sparkline values={m.trend} tone={m.status === 'danger' ? 'danger' : 'accent'} height={22} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>
      <Sheet open={!!open} onClose={() => setOpen(null)} title={open?.name} subtitle={open?.roleLabel}>
        {open && (
          <div className="flex flex-col gap-5">
            <dl className="grid grid-cols-2 gap-4">
              <Field label="Звонки сегодня">
                {open.callsToday} из {open.callsNorm}
              </Field>
              <Field label="Время разговоров">{open.talkMin} мин</Field>
              <Field label="Сделок в работе">{open.deals}</Field>
              <Field label="Сумма воронки">{rubShort(open.pipeline)}</Field>
            </dl>
            <div>
              <div className="mb-2 text-xs text-muted">Звонки за 10 дней</div>
              <Sparkline values={open.trend} height={56} tone={open.status === 'danger' ? 'danger' : 'accent'} />
            </div>
            <Card className="bg-surface-2/50">
              <div className="flex items-center gap-2 text-sm font-medium text-ink">
                <Sparkles size={14} className="text-accent" /> Вывод копилота
              </div>
              <p className="mt-1.5 text-sm text-ink-2">{open.note}. Подробности — в разборе звонков и сделках менеджера.</p>
            </Card>
            <Button variant="secondary" onClick={() => navigate(withQuery('/sales/calls', { manager: String(open.id) }))}>
              Звонки менеджера
            </Button>
          </div>
        )}
      </Sheet>
    </>
  )
}

function DealsTab() {
  const { data: funnels } = useFunnels()
  const { data: deals } = useDeals()
  const [funnel, setFunnel] = useState<string | null>(null)
  if (!funnels || !deals) return <Skeleton className="h-96" />
  const current = funnels.find((f) => f.id === funnel) ?? funnels[0]
  const inFunnel = deals.filter((d) => d.funnel === current.id)
  const forgotten = deals.filter((d) => d.daysIdle >= 10).sort((a, b) => b.daysIdle - a.daysIdle)
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented options={funnels.map((f) => ({ id: f.id, label: f.name }))} value={current.id} onChange={setFunnel} />
        <span className="num text-sm text-muted">
          {count(inFunnel.length, ['сделка', 'сделки', 'сделок'])} · {rubShort(inFunnel.reduce((s, d) => s + d.amount, 0))}
        </span>
      </div>
      <div className="no-scrollbar -mx-4 flex gap-3 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0">
        {current.stages.map((stage) => {
          const items = inFunnel.filter((d) => d.stage === stage.id)
          return (
            <div key={stage.id} className="flex min-w-[220px] flex-1 flex-col rounded-lg bg-surface-2/60 p-2">
              <div className="flex items-center justify-between px-1.5 pt-1 pb-2">
                <span className="flex items-center gap-1.5 text-sm font-medium text-ink">
                  <Dot tone={stage.tone} />
                  {stage.name}
                </span>
                <span className="num text-xs text-muted">{items.length}</span>
              </div>
              <div className="flex flex-col gap-2">
                {items.map((d) => (
                  <Card key={d.id} className="!p-3" interactive>
                    <div className="line-clamp-2 text-sm font-medium text-ink">{d.title}</div>
                    <div className="mt-1 text-xs text-muted">{d.manager}</div>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="num text-sm font-medium text-ink">{rubShort(d.amount)}</span>
                      {d.daysIdle >= 7 ? (
                        <Badge tone={d.daysIdle >= 10 ? 'danger' : 'warning'}>{d.daysIdle} дн без движения</Badge>
                      ) : (
                        <span className="text-xs text-faint">{d.nextStep}</span>
                      )}
                    </div>
                  </Card>
                ))}
                {!items.length && <div className="px-2 py-6 text-center text-xs text-faint">Пусто</div>}
              </div>
            </div>
          )
        })}
      </div>
      <Card padded={false}>
        <div className="px-4 pt-4">
          <CardHeader title="Забытые клиенты" hint="Сделки без звонков, писем и задач 10 дней и дольше" />
        </div>
        <ul className="divide-y divide-line border-t border-line">
          {forgotten.slice(0, 6).map((d) => (
            <li key={d.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
              <span className="min-w-0 flex-1 truncate text-ink">{d.client}</span>
              <span className="hidden truncate text-muted md:block md:w-64">{d.title}</span>
              <span className="w-36 truncate text-muted">{d.manager}</span>
              <span className="num w-24 text-right text-ink">{rubShort(d.amount)}</span>
              <Badge tone="danger">{d.daysIdle} дн</Badge>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}

function CallsTab() {
  const { query } = useRoute()
  const manager = query.get('manager')
  const { data } = useCalls(manager)
  const linked = Number(query.get('id')) || null
  const [openId, setOpenId] = useState<number | null>(linked)
  if (!data) return <Skeleton className="h-96" />
  const list = data
  return (
    <>
      <Card padded={false}>
        {manager && (
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5 text-sm">
            <span className="text-muted">Звонки менеджера: {list[0]?.manager ?? '—'} · сегодня и в прошлый рабочий день</span>
            <Button size="sm" variant="ghost" onClick={() => navigate('/sales/calls')}>
              Показать всех
            </Button>
          </div>
        )}
        {list.length === 0 ? (
          <Empty title="Звонков нет" text="За выбранный период у менеджера нет звонков" />
        ) : (
          <ul className="divide-y divide-line">
            {list.map((c) => (
              <CallRow key={c.id} call={c} onOpen={() => c.score !== null && setOpenId(c.id)} />
            ))}
          </ul>
        )}
      </Card>
      <CallSheet
        id={openId}
        onClose={() => {
          setOpenId(null)
          if (linked) navigate(withQuery('/sales/calls', { manager }), { replace: true })
        }}
      />
    </>
  )
}

function scoreTone(score: number): Tone {
  return score >= 75 ? 'success' : score >= 60 ? 'warning' : 'danger'
}

function CallRow({ call, onOpen }: { call: Call; onOpen: () => void }) {
  return (
    <li>
      <button
        onClick={onOpen}
        disabled={call.score === null}
        title={call.score === null ? 'Разбор есть только у записанных разговоров длиннее минуты' : undefined}
        className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors enabled:hover:bg-surface-2/60"
      >
        <span
          className={clsx(
            'grid size-7 shrink-0 place-items-center rounded-md',
            call.missed ? 'bg-danger-soft text-danger' : 'bg-surface-2 text-muted',
          )}
        >
          {call.missed ? <PhoneMissed size={14} /> : call.direction === 'in' ? <ArrowDownLeft size={14} /> : <ArrowUpRight size={14} />}
        </span>
        <span className="num w-12 text-muted">{call.at}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium text-ink">{call.client}</span>
          <span className="block truncate text-xs text-muted">
            {call.manager} · {call.outcome}
          </span>
        </span>
        <span className="num hidden w-12 text-right text-muted sm:block">{call.missed ? '—' : duration(call.durationSec)}</span>
        <span className="w-14 text-right">
          {call.score !== null ? <Badge tone={scoreTone(call.score)}>{call.score}</Badge> : <span className="text-faint">—</span>}
        </span>
      </button>
    </li>
  )
}

function CallSheet({ id, onClose }: { id: number | null; onClose: () => void }) {
  const { data } = useCallReview(id)
  const [playing, setPlaying] = useState(false)
  const toast = useToast()
  return (
    <Sheet
      open={id !== null}
      onClose={onClose}
      width={640}
      title={data ? `Разбор звонка · ${data.call.client}` : 'Разбор звонка'}
      subtitle={data && `${data.call.manager} · ${duration(data.call.durationSec)} · ${data.call.outcome}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Закрыть
          </Button>
          <Button onClick={() => toast('Звонок добавлен в план планёрки', 'success')}>На планёрку</Button>
        </>
      }
    >
      {!data ? (
        <Skeleton className="h-96" />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex items-center gap-3 rounded-lg border border-line p-3">
            <button
              aria-label={playing ? 'Пауза' : 'Слушать запись'}
              onClick={() => setPlaying((p) => !p)}
              className="grid size-9 shrink-0 place-items-center rounded-full bg-accent text-accent-fg"
            >
              <Play size={15} className="ml-0.5" />
            </button>
            <div className="flex h-9 flex-1 items-center gap-[2px]">
              {data.waveform.map((v, i) => (
                <span
                  key={i}
                  className={clsx('flex-1 rounded-full', i < 38 ? 'bg-accent' : 'bg-surface-3')}
                  style={{ height: `${v * 100}%` }}
                />
              ))}
            </div>
            <Ring value={data.call.score ?? 0} max={100} size={44} tone={scoreTone(data.call.score ?? 0)}>
              {data.call.score}
            </Ring>
          </div>

          <p className="text-sm text-ink-2">{data.summary}</p>

          <section>
            <h4 className="mb-2 text-sm font-medium text-ink">Критерии</h4>
            <ul className="flex flex-col gap-2.5">
              {data.criteria.map((c) => (
                <li key={c.key}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-ink">{c.label}</span>
                    <span className="num text-muted">
                      {c.score} / {c.max}
                    </span>
                  </div>
                  <Meter value={c.score} max={c.max} tone={scoreTone((c.score / c.max) * 100)} className="mt-1" />
                  <div className="mt-1 text-xs text-muted">
                    {c.comment}
                    {c.quote && <span className="text-ink-2"> — «{c.quote}»</span>}
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h4 className="mb-2 text-sm font-medium text-ink">Что улучшить</h4>
            <ul className="flex flex-col gap-1.5">
              {data.advice.map((a) => (
                <li key={a} className="flex gap-2 text-sm text-ink-2">
                  <Sparkles size={14} className="mt-0.5 shrink-0 text-accent" />
                  {a}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h4 className="mb-2 text-sm font-medium text-ink">Расшифровка</h4>
            <ol className="transcript flex flex-col gap-2">
              {data.transcript.map((l, i) => (
                <li key={i} className="flex gap-3 text-sm">
                  <span className="mono w-10 shrink-0 pt-px text-xs text-faint">{duration(l.t)}</span>
                  <span className={clsx('w-16 shrink-0 text-xs pt-0.5', l.speaker === 'manager' ? 'text-accent' : 'text-muted')}>
                    {l.speaker === 'manager' ? 'Менеджер' : 'Клиент'}
                  </span>
                  <span className="text-ink-2">{l.mark ? <mark>{l.text}</mark> : l.text}</span>
                </li>
              ))}
            </ol>
          </section>
        </div>
      )}
    </Sheet>
  )
}
