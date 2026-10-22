import clsx from 'clsx'
import { ArrowDown, ChevronDown, PencilLine } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useAgents, useBudget, useDocsGraph, useLastTrace, type AgentsInfo } from '@/api/queries'
import { GITHUB_URL } from '@/app/nav'
import { navigate } from '@/app/router'
import { Meter } from '@/ui/charts'
import { ms, num, usd } from '@/ui/format'
import { GithubIcon } from '@/ui/icons'
import { Badge, Button, Card, CardHeader, Empty, PageHeader, Skeleton } from '@/ui/kit'
import { TraceTimeline } from '@/ui/Trace'

const STACK = [
  'Python 3.12',
  'FastAPI',
  'SQLite (WAL, FTS5)',
  'LangGraph',
  'Hermes Agent',
  'MCP',
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
  const { data: agents } = useAgents()
  return (
    <>
      <PageHeader
        eyebrow="ИИ-слой"
        title="Под капотом"
        description="Как устроена платформа: модули работают с CRM и 1С только через порты, агент берёт данные из одного реестра инструментов, документы идут по графу LangGraph, на модели — жёсткий суточный бюджет."
        actions={
          <Button
            variant="secondary"
            icon={<GithubIcon size={14} />}
            onClick={() => window.open(GITHUB_URL, '_blank', 'noopener')}
          >
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
              <CardHeader
                title="Бюджет ИИ за сутки"
                hint="Жёсткий потолок. Сверх него работают ответы без модели"
              />
              <div className="num text-xl font-semibold text-ink">
                {usd(budget.spentUsd)}{' '}
                <span className="text-base font-normal text-muted">из {usd(budget.capUsd)}</span>
              </div>
              <Meter value={budget.spentUsd} max={budget.capUsd} className="mt-2" />
              <div className="mt-4 flex h-16 items-end gap-[3px]">
                {budget.byHour.map((v, h) => (
                  <span
                    key={h}
                    title={`${h}:00 — ${v} запросов к модели`}
                    className={clsx('flex-1 rounded-t-[2px]', v ? 'bg-accent' : 'bg-surface-3')}
                    style={{ height: `${Math.max(4, (v / Math.max(1, ...budget.byHour)) * 100)}%` }}
                  />
                ))}
              </div>
              <div className="num mt-1 flex justify-between text-[10px] text-faint">
                <span>00</span>
                <span>12</span>
                <span>23</span>
              </div>
              <p className="mt-3 text-xs text-muted">
                {budget.modelConnected
                  ? `Лимит на посетителя: ${budget.questionsCap} свободных вопросов и ${budget.documentsCap} документа в сутки. В расход идёт стоимость, которую вернул провайдер.`
                  : 'Модель сейчас не подключена: работают готовые ответы, регламенты и разбор документов правилами.'}
              </p>
            </Card>
          )}
          {agents && <ToolsCard info={agents} />}
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
          <>
            <CardHeader title="Трассировка хода агента" />
            <Empty
              title="Сегодня вопросов ещё не было"
              text="Задайте вопрос в Копилоте — здесь появится его ход: какие инструменты вызывались, сколько это заняло и стоило."
              action={<Button onClick={() => navigate('/copilot')}>Открыть Копилот</Button>}
            />
          </>
        ) : (
          <>
            <CardHeader
              title="Трассировка последнего хода"
              hint={`«${run.question}» · ${run.startedAgo}`}
              action={
                <div className="hidden flex-wrap items-center justify-end gap-1.5 sm:flex">
                  <Badge tone="accent">{run.engineLabel}</Badge>
                  {run.model && <Badge>{run.model.split('/').pop()}</Badge>}
                  <Badge>{ms(run.totalMs)}</Badge>
                  {run.tokens > 0 && <Badge>{num(run.tokens)} токенов</Badge>}
                  <Badge tone="success">{run.costUsd ? usd(run.costUsd) : 'бесплатно'}</Badge>
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
          hint="На решении человека граф останавливается через interrupt(); состояние лежит в SQLite, и работа продолжается с того же места — хоть через день"
        />
        <DocGraph />
      </Card>
    </>
  )
}

function Box({
  title,
  sub,
  tone = 'neutral',
}: {
  title: string
  sub?: string
  tone?: 'neutral' | 'accent' | 'muted'
}) {
  return (
    <div
      className={clsx(
        'rounded-md border px-3 py-2',
        tone === 'accent'
          ? 'border-accent/40 bg-accent-soft'
          : tone === 'muted'
            ? 'border-dashed border-line-strong bg-surface'
            : 'border-line bg-surface-2/70',
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
        <Box title="Telegram Mini App" sub="та же веб-версия" />
        <Box title="Telegram-бот" sub="aiogram 3" />
      </Layer>
      <Arrow />
      <Layer label="ИИ-слой">
        <Box title="Hermes Agent" sub="/v1/runs · SSE" tone="accent" />
        <Box title="Встроенный цикл" sub="запасной путь" tone="accent" />
        <Box title="Реестр инструментов" sub="MCP · 11 инструментов" tone="accent" />
        <Box title="Бюджет" sub="$1,5 / сутки" />
      </Layer>
      <Arrow />
      <Layer label="Модули">
        <Box title="Продажи" sub="signals · call_quality" />
        <Box title="Документы" sub="LangGraph · checks" />
        <Box title="Знания" sub="FTS5 · BM25" />
        <Box title="Интеграции" sub="sync · сверка" />
      </Layer>
      <Arrow />
      <Layer label="Порты">
        <Box title="CrmPort" sub="только чтение" />
        <Box title="ErpPort" sub="только чтение" />
        <Box title="core.llm" sub="бюджет на каждый вызов" />
      </Layer>
      <Arrow />
      <Layer label="Адаптеры">
        <Box title="Эмулятор Битрикс24" sub="CRM_MODE=emulator" />
        <Box title="Битрикс24 REST" sub="CRM_MODE=live" tone="muted" />
        <Box title="Эмулятор 1С" sub="OData-формат" />
        <Box title="1С OData" sub="ERP_MODE=live" tone="muted" />
        <Box title="OpenRouter" sub="DeepSeek · Gemini" />
      </Layer>
    </div>
  )
}

function ToolsCard({ info }: { info: AgentsInfo }) {
  const [open, setOpen] = useState(false)
  return (
    <Card>
      <CardHeader
        title={`Инструменты агента · ${info.tools.length}`}
        hint={`Один реестр для встроенного цикла, Hermes (через MCP) и бота. Hermes ${info.hermes ? 'подключён' : 'сейчас не подключён — отвечает встроенный цикл'}`}
      />
      <ul className="flex flex-col gap-1">
        {(open ? info.tools : info.tools.slice(0, 5)).map((t) => (
          <li key={t.name} className="flex items-start gap-2 text-xs">
            <span className="mono shrink-0 text-ink">{t.name}</span>
            {t.writes && (
              <span title="Создаёт только черновик — решает человек" className="shrink-0 text-warning">
                <PencilLine size={12} />
              </span>
            )}
            <span className="truncate text-muted" title={t.description}>
              {t.description}
            </span>
          </li>
        ))}
      </ul>
      <button
        onClick={() => setOpen((o) => !o)}
        className="mt-2 inline-flex cursor-pointer items-center gap-1 text-xs text-accent"
      >
        {open ? 'Свернуть' : 'Все инструменты'}
        <ChevronDown size={12} className={clsx('transition-transform', open && 'rotate-180')} />
      </button>
    </Card>
  )
}

/** The graph of `modules/docs/graph.py`; the mermaid text under it is generated by LangGraph from the code. */
function DocGraph() {
  const { data } = useDocsGraph()
  const [source, setSource] = useState(false)
  const box = (x: number, y: number, label: string, sub: string, human = false) => (
    <g>
      <rect
        x={x}
        y={y}
        width={130}
        height={56}
        rx={8}
        fill={human ? 'var(--warning-soft)' : 'var(--surface-2)'}
        stroke={human ? 'var(--warning)' : 'var(--border-strong)'}
      />
      <text
        x={x + 65}
        y={y + 24}
        textAnchor="middle"
        className="fill-[var(--text)] font-mono text-[13px] font-medium"
      >
        {label}
      </text>
      <text x={x + 65} y={y + 42} textAnchor="middle" className="fill-[var(--muted)] text-[11px]">
        {sub}
      </text>
    </g>
  )
  const edge = (d: string, color = 'var(--faint)', dash = false) => (
    <path
      d={d}
      fill="none"
      stroke={color}
      strokeWidth="1.2"
      strokeDasharray={dash ? '4 3' : undefined}
      markerEnd="url(#arr)"
    />
  )
  const note = (x: number, y: number, text: string, color = 'var(--muted)') => (
    <text x={x} y={y} textAnchor="middle" fill={color} className="text-[11px]">
      {text}
    </text>
  )
  return (
    <div>
      <div className="overflow-x-auto">
        <svg
          viewBox="0 0 760 200"
          className="min-w-[640px]"
          role="img"
          aria-label="Граф: extract, validate, review, post, reject"
        >
          <defs>
            <marker
              id="arr"
              viewBox="0 0 8 8"
              refX="7"
              refY="4"
              markerWidth="7"
              markerHeight="7"
              orient="auto"
            >
              <path d="M0,0 L8,4 L0,8 z" fill="var(--faint)" />
            </marker>
          </defs>
          {note(32, 108, 'START', 'var(--faint)')}
          {edge('M56,104 L76,104')}
          {box(80, 76, 'extract', 'тип и реквизиты')}
          {edge('M210,104 L246,104')}
          {box(250, 76, 'validate', 'сверка 1С · CRM')}
          {edge('M380,104 L436,104', 'var(--warning)')}
          {note(408, 96, 'не так', 'var(--warning)')}
          {box(440, 76, 'review', 'interrupt()', true)}
          {edge('M315,76 C315,14 675,14 675,36', 'var(--success)', true)}
          {note(495, 24, 'все проверки прошли — человек не нужен', 'var(--success)')}
          {box(610, 40, 'post', 'проводка')}
          {edge('M570,94 L606,76', 'var(--success)')}
          {note(588, 70, 'провести', 'var(--success)')}
          {box(610, 130, 'reject', 'отклонён')}
          {edge('M570,116 L606,148', 'var(--danger)')}
          {note(578, 152, 'отклонить', 'var(--danger)')}
        </svg>
      </div>
      {data && (
        <div className="mt-2">
          <button
            onClick={() => setSource((v) => !v)}
            className="inline-flex cursor-pointer items-center gap-1 text-xs text-accent"
          >
            Описание графа, которое LangGraph строит из кода (mermaid)
            <ChevronDown size={12} className={clsx('transition-transform', source && 'rotate-180')} />
          </button>
          {source && (
            <pre className="mono mt-2 max-h-72 overflow-auto rounded-md bg-surface-2/70 p-3 text-[11px] leading-5 text-ink-2">
              {data.mermaid}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
