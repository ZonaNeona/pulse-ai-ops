import clsx from 'clsx'
import { ArrowDown } from 'lucide-react'
import { GithubIcon } from '@/ui/icons'
import type { ReactNode } from 'react'
import { useBudget, useLastTrace } from '@/api/queries'
import { GITHUB_URL } from '@/app/nav'
import { Meter } from '@/ui/charts'
import { ms, num, usd } from '@/ui/format'
import { Badge, Button, Card, CardHeader, PageHeader, Skeleton } from '@/ui/kit'
import { TraceTimeline } from '@/ui/Trace'

const STACK = [
  'Python 3.12',
  'FastAPI',
  'SQLite (WAL)',
  'Hermes Agent',
  'MCP',
  'LangGraph',
  'OpenRouter',
  'aiogram 3',
  'React 19',
  'TypeScript',
  'Tailwind v4',
  'TanStack Query',
  'GitHub Actions',
]

export function UnderTheHood() {
  const { data: run } = useLastTrace()
  const { data: budget } = useBudget()
  return (
    <>
      <PageHeader
        eyebrow="ИИ-слой"
        title="Под капотом"
        description="Как устроена платформа: порты и адаптеры, агент Hermes с инструментами через MCP, граф LangGraph для документов, жёсткий бюджет на модели."
        actions={
          <Button variant="secondary" icon={<GithubIcon size={14} />} onClick={() => window.open(GITHUB_URL, '_blank', 'noopener')}>
            Код на GitHub
          </Button>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader title="Архитектура" hint="Модули говорят с внешними системами только через порты" />
          <Architecture />
        </Card>
        <div className="flex flex-col gap-4">
          {!budget ? (
            <Skeleton className="h-52" />
          ) : (
            <Card>
              <CardHeader title="Бюджет ИИ за сутки" hint="Жёсткий потолок, сверх него — ответы из кэша" />
              <div className="num text-xl font-semibold text-ink">
                {usd(budget.spentUsd)} <span className="text-base font-normal text-muted">из {usd(budget.capUsd)}</span>
              </div>
              <Meter value={budget.spentUsd} max={budget.capUsd} className="mt-2" />
              <div className="mt-4 flex h-16 items-end gap-[3px]">
                {budget.byHour.map((v, h) => (
                  <span
                    key={h}
                    title={`${h}:00 — ${v} запросов`}
                    className={clsx('flex-1 rounded-t-[2px]', v ? 'bg-accent' : 'bg-surface-3')}
                    style={{ height: `${Math.max(4, (v / Math.max(...budget.byHour)) * 100)}%` }}
                  />
                ))}
              </div>
              <div className="num mt-1 flex justify-between text-[10px] text-faint">
                <span>00</span>
                <span>12</span>
                <span>23</span>
              </div>
              <p className="mt-3 text-xs text-muted">
                Лимит на посетителя: {budget.questionsCap} вопросов и {budget.documentsCap} документа в сутки.
              </p>
            </Card>
          )}
          <Card>
            <CardHeader title="Стек" />
            <div className="flex flex-wrap gap-1.5">
              {STACK.map((s) => (
                <Badge key={s}>{s}</Badge>
              ))}
            </div>
          </Card>
        </div>
      </div>

      <Card className="mt-4">
        {!run ? (
          <Skeleton className="h-72" />
        ) : (
          <>
            <CardHeader
              title="Трассировка хода агента · пример"
              hint={`«${run.question}» — живая трассировка появится с подключением Hermes Agent`}
              action={
                <div className="hidden items-center gap-1.5 sm:flex">
                  <Badge tone="accent">{run.engine === 'hermes' ? 'Hermes Agent' : 'Резервный цикл'}</Badge>
                  <Badge>{run.model}</Badge>
                  <Badge>{ms(run.totalMs)}</Badge>
                  <Badge>{num(run.tokens)} токенов</Badge>
                  <Badge tone="success">{usd(run.costUsd)}</Badge>
                </div>
              }
            />
            <TraceTimeline run={run} />
          </>
        )}
      </Card>

      <Card className="mt-4">
        <CardHeader
          title="Граф обработки документа (LangGraph)"
          hint="Состояние сохраняется в SQLite: граф можно остановить на подтверждении и продолжить через день"
        />
        <DocGraph />
      </Card>
    </>
  )
}

function Box({ title, sub, tone = 'neutral', className }: { title: string; sub?: string; tone?: 'neutral' | 'accent' | 'muted'; className?: string }) {
  return (
    <div
      className={clsx(
        'rounded-md border px-3 py-2',
        tone === 'accent' ? 'border-accent/40 bg-accent-soft' : tone === 'muted' ? 'border-dashed border-line-strong bg-surface' : 'border-line bg-surface-2/70',
        className,
      )}
    >
      <div className="text-sm font-medium text-ink">{title}</div>
      {sub && <div className="mono mt-0.5 text-[11px] text-muted">{sub}</div>}
    </div>
  )
}

function Layer({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-2 sm:grid-cols-[110px_minmax(0,1fr)] sm:items-center">
      <div className="text-xs font-medium text-faint">{label}</div>
      <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))' }}>
        {children}
      </div>
    </div>
  )
}

const Arrow = () => (
  <div className="flex justify-center py-1 text-faint sm:pl-[110px]">
    <ArrowDown size={14} />
  </div>
)

function Architecture() {
  return (
    <div className="flex flex-col">
      <Layer label="Каналы">
        <Box title="Веб-приложение" sub="React 19" />
        <Box title="Telegram Mini App" sub="initData HMAC" />
        <Box title="Telegram-бот" sub="aiogram 3" />
      </Layer>
      <Arrow />
      <Layer label="ИИ-слой">
        <Box title="Hermes Agent" sub="/v1/runs · SSE" tone="accent" />
        <Box title="MCP-сервер" sub="23 инструмента" tone="accent" />
        <Box title="LangGraph" sub="граф документов" tone="accent" />
        <Box title="Бюджет и кэш" sub="$1,5 / сутки" />
      </Layer>
      <Arrow />
      <Layer label="Модули">
        <Box title="Продажи" sub="signals · call_quality" />
        <Box title="Документы" sub="extract · reconcile" />
        <Box title="Знания" sub="FTS5 · BM25" />
        <Box title="Интеграции" sub="sync · webhooks" />
      </Layer>
      <Arrow />
      <Layer label="Порты">
        <Box title="CrmPort" sub="read · drafts" />
        <Box title="ErpPort" sub="read" />
        <Box title="LlmPort" sub="OpenAI-совместимый" />
      </Layer>
      <Arrow />
      <Layer label="Адаптеры">
        <Box title="Эмулятор Битрикс24" sub="CRM_MODE=emulator" />
        <Box title="Битрикс24 REST" sub="CRM_MODE=live" tone="muted" />
        <Box title="Эмулятор 1С" sub="OData-формат" />
        <Box title="OpenRouter" sub="DeepSeek · Gemini" />
      </Layer>
    </div>
  )
}

function DocGraph() {
  const nodes = [
    { id: 'classify', x: 20, label: 'classify', sub: 'тип документа' },
    { id: 'extract', x: 170, label: 'extract', sub: 'поля + уверенность' },
    { id: 'validate', x: 320, label: 'validate', sub: 'сверка 1С / CRM' },
    { id: 'review', x: 470, label: 'review', sub: 'interrupt()', human: true },
    { id: 'draft', x: 620, label: 'draft', sub: 'проводка в 1С' },
  ]
  return (
    <div className="overflow-x-auto">
      <svg viewBox="0 0 760 170" className="min-w-[640px]" role="img" aria-label="Граф: classify, extract, validate, review, draft">
        <defs>
          <marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L8,4 L0,8 z" fill="var(--faint)" />
          </marker>
        </defs>
        <text x="20" y="20" className="fill-[var(--faint)] text-[11px]">
          START
        </text>
        {nodes.slice(0, -1).map((n, i) => (
          <line
            key={n.id}
            x1={n.x + 120}
            y1={80}
            x2={nodes[i + 1].x - 4}
            y2={80}
            stroke="var(--faint)"
            strokeWidth="1.2"
            markerEnd="url(#arr)"
          />
        ))}
        {/* validate → draft when everything matches and confidence is high */}
        <path d="M380,110 C380,150 680,150 680,112" fill="none" stroke="var(--success)" strokeWidth="1.2" strokeDasharray="4 3" markerEnd="url(#arr)" />
        <text x="530" y="160" textAnchor="middle" className="fill-[var(--success)] text-[11px]">
          всё совпало и уверенность ≥ 0,95
        </text>
        {/* review → extract when a human corrects fields */}
        <path d="M530,50 C530,10 230,10 230,48" fill="none" stroke="var(--warning)" strokeWidth="1.2" strokeDasharray="4 3" markerEnd="url(#arr)" />
        <text x="380" y="18" textAnchor="middle" className="fill-[var(--warning)] text-[11px]">
          человек исправил поля
        </text>
        {nodes.map((n) => (
          <g key={n.id}>
            <rect
              x={n.x}
              y={50}
              width={120}
              height={60}
              rx={8}
              fill={n.human ? 'var(--warning-soft)' : 'var(--surface-2)'}
              stroke={n.human ? 'var(--warning)' : 'var(--border-strong)'}
            />
            <text x={n.x + 60} y={76} textAnchor="middle" className="fill-[var(--text)] font-mono text-[13px] font-medium">
              {n.label}
            </text>
            <text x={n.x + 60} y={94} textAnchor="middle" className="fill-[var(--muted)] text-[11px]">
              {n.sub}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}
