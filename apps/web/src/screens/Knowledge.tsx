import { Fragment, useState, type FormEvent, type ReactNode } from 'react'
import clsx from 'clsx'
import { ArrowUp, BookOpen, FileText, Loader2, ShieldCheck, Sparkles } from 'lucide-react'
import type { KbAnswer } from '@/api/types'
import { askKb, useKbAnswer, useKbStats } from '@/api/queries'
import { Badge, Card, CardHeader, Notice, PageHeader, Skeleton } from '@/ui/kit'
import { useToast } from '@/ui/Toast'

const DOCS = [
  ['Ценовая политика 2026', 14],
  ['Регламент согласования сделок', 9],
  ['Гарантийные обязательства', 11],
  ['Стандарт монтажа ВК и ОВ', 42],
  ['Работа с рекламациями', 8],
  ['Скрипты первого звонка', 6],
  ['Складской регламент отпуска ТМЦ', 12],
  ['Положение о командировках инженеров', 10],
  ['Регламент шеф-монтажных работ', 15],
  ['Положение об абонентском сервисе', 16],
] as const

const PRESETS = [
  { label: 'Скидка дилеру', query: 'Какая скидка допустима для дилера без согласования с директором?' },
  { label: 'Гарантия на монтаж', query: 'Какой срок гарантии на монтажные работы?' },
  { label: 'Опрессовка отопления', query: 'Какое давление используется при опрессовке систем отопления?' },
  { label: 'Выезд по рекламации', query: 'В течение какого времени инженер выезжает на объект по рекламации?' },
  { label: 'Марка кофе (ловушка)', query: 'Какая марка кофе закупается на кухню офиса?' },
]

/** Renders «текст [1] текст» with superscript clickable source markers. */
function withCitations(text: string, onCite: (n: number) => void): ReactNode[] {
  return text.split(/(\[\d+\])/).map((part, i) => {
    const m = /^\[(\d+)\]$/.exec(part)
    if (!m) return <Fragment key={i}>{part}</Fragment>
    const n = Number(m[1])
    return (
      <button
        key={i}
        onClick={() => onCite(n)}
        aria-label={`Источник ${n}`}
        className="mx-0.5 inline-grid h-[18px] min-w-[18px] place-items-center rounded-sm border border-accent/30 bg-accent-soft px-1 align-[2px] text-[11px] leading-none font-semibold text-accent hover:bg-accent hover:text-accent-fg"
      >
        {n}
      </button>
    )
  })
}

export function Knowledge() {
  const { data: stats } = useKbStats()
  const { data: defaultAnswer } = useKbAnswer()
  const [active, setActive] = useState<number | null>(1)
  const [question, setQuestion] = useState('')
  const [customAnswer, setCustomAnswer] = useState<KbAnswer | null>(null)
  const [loading, setLoading] = useState(false)
  const toast = useToast()

  const answer = customAnswer ?? defaultAnswer

  const handleAsk = async (text: string) => {
    const q = text.trim()
    if (!q) return
    setLoading(true)
    try {
      const resp = await askKb(q)
      setCustomAnswer(resp)
      setActive(resp.sources.length > 0 ? 1 : null)
      if (!resp.grounded) {
        toast('Вопрос вне регламентов компании — сформирован честный отказ', 'neutral')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка поиска по базе знаний'
      toast(msg, 'danger')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    handleAsk(question)
  }

  const handlePreset = (queryText: string) => {
    setQuestion(queryText)
    handleAsk(queryText)
  }

  return (
    <>
      <PageHeader
        eyebrow="Модуль · Знания"
        title="База знаний компании"
        description="Ответы только по регламентам: каждое утверждение со ссылкой на фрагмент. Нет источника — ассистент честно говорит «не знаю»."
      />
      <Notice tone="neutral" className="mb-4">
        <div className="flex w-full flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex size-2 shrink-0 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-semibold text-ink">RAG-конвейер активен:</span>
            <span className="text-muted">
              FTS5 полнотекстовый индекс + BM25, цитирование фрагментов, защита от галлюцинаций
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-2 text-xs text-muted">
            <span>Faithfulness eval: 19/20</span>
            <span>•</span>
            <span>Отказы 5/5</span>
          </div>
        </div>
      </Notice>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex min-w-0 flex-col gap-4">
          <div className="flex flex-col gap-2">
            <form
              onSubmit={handleSubmit}
              className="flex items-center gap-2 rounded-lg border border-line bg-surface p-1.5 pl-4 shadow-card focus-within:border-accent"
            >
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Например: какой срок гарантии на монтаж?"
                className="h-9 flex-1 bg-transparent text-base outline-none placeholder:text-faint"
              />
              <button
                type="submit"
                disabled={loading}
                aria-label="Спросить"
                className="grid size-9 place-items-center rounded-md bg-accent text-accent-fg disabled:opacity-50"
              >
                {loading ? <Loader2 size={16} className="animate-spin" /> : <ArrowUp size={16} />}
              </button>
            </form>
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="flex items-center gap-1 text-muted">
                <Sparkles size={12} className="text-accent" />
                Примеры:
              </span>
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => handlePreset(p.query)}
                  className="rounded-full border border-line bg-surface px-2.5 py-0.5 text-ink hover:border-accent hover:text-accent transition-colors"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {!answer ? (
            <Skeleton className="h-64" />
          ) : (
            <Card>
              <div className="text-sm font-medium text-muted">{answer.question}</div>
              <p className="mt-2 text-md leading-7 text-ink">{withCitations(answer.answer, setActive)}</p>
              <div className="mt-3 flex items-center gap-2">
                {answer.grounded ? (
                  <Badge tone="success" dot>
                    Опирается на {answer.sources.length}{' '}
                    {answer.sources.length === 1 ? 'источник' : answer.sources.length < 5 ? 'источника' : 'источников'}
                  </Badge>
                ) : (
                  <Badge tone="warning" dot>
                    Честный отказ: вне регламентов компании
                  </Badge>
                )}
              </div>
              {answer.sources.length > 0 && (
                <ul className="mt-4 flex flex-col gap-2 border-t border-line pt-4">
                  {answer.sources.map((s) => (
                    <li key={s.id}>
                      <button
                        onClick={() => setActive(s.id)}
                        className={clsx(
                          'w-full rounded-md border px-3 py-2.5 text-left transition-colors',
                          active === s.id ? 'border-accent bg-accent-soft/40' : 'border-line hover:border-line-strong',
                        )}
                      >
                        <div className="flex items-center gap-2 text-sm font-medium text-ink">
                          <span className="grid size-4 place-items-center rounded-sm bg-accent-soft text-[10px] font-semibold text-accent">
                            {s.id}
                          </span>
                          {s.title}
                          <span className="font-normal text-muted">· {s.section}</span>
                        </div>
                        <p className="mt-1 text-sm text-ink-2">«{s.quote}»</p>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}
        </div>

        <div className="flex flex-col gap-4">
          {!stats ? (
            <Skeleton className="h-48" />
          ) : (
            <Card>
              <CardHeader
                title="Качество ответов"
                hint="Прогон eval на эталонных вопросах"
                icon={<ShieldCheck size={16} />}
              />
              <dl className="grid grid-cols-2 gap-3">
                <Metric label="С источником" value={`${stats.grounded}%`} />
                <Metric label="Эталоны" value={`${stats.evalPassed} / ${stats.evalTotal}`} />
                <Metric label="Честное «не знаю»" value={`${stats.refusalsCorrect} / ${stats.refusalsTotal}`} />
                <Metric label="Фрагментов" value={String(stats.chunks)} />
              </dl>
            </Card>
          )}
          <Card padded={false}>
            <div className="px-4 pt-4">
              <CardHeader
                title="Документы в базе"
                hint={`${stats?.documents ?? '24'} регламента, FTS5 + цитаты`}
                icon={<BookOpen size={16} />}
              />
            </div>
            <ul className="divide-y divide-line border-t border-line">
              {DOCS.map(([title, chunks]) => (
                <li key={title} className="flex items-center gap-2.5 px-4 py-2.5 text-sm">
                  <FileText size={14} className="text-faint" />
                  <span className="flex-1 truncate text-ink-2">{title}</span>
                  <span className="num text-xs text-muted">{chunks}</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-surface-2/70 px-3 py-2.5">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="num mt-0.5 text-md font-semibold text-ink">{value}</dd>
    </div>
  )
}
