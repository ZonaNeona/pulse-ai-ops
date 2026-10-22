import { Fragment, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import clsx from 'clsx'
import { ArrowUp, BookOpen, FileText, Loader2, ShieldCheck, Sparkles } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import type { KbAnswer } from '@/api/types'
import { askKb, useKbDocuments, useKbStats } from '@/api/queries'
import { useRoute } from '@/app/router'
import { count, usd } from '@/ui/format'
import { Badge, Card, CardHeader, Empty, PageHeader, Skeleton, type Tone } from '@/ui/kit'
import { useToast } from '@/ui/Toast'

const PRESETS = [
  { label: 'Скидка дилеру', query: 'Какую скидку менеджер может дать дилеру без согласования?' },
  { label: 'Гарантия на монтаж', query: 'Какая гарантия на монтажные работы?' },
  { label: 'Опрессовка', query: 'Каким давлением делают опрессовку отопления?' },
  { label: 'Выезд по аварии', query: 'Как быстро инженер выезжает в клинику по аварии?' },
  { label: 'Вне базы', query: 'Какой кофе закупают на кухню офиса?' },
]

const MODE: Record<KbAnswer['mode'], { label: string; tone: Tone }> = {
  model: { label: 'Ответ модели по найденным разделам, ссылки проверены кодом', tone: 'success' },
  extract: { label: 'Выдержки из регламентов, без модели', tone: 'info' },
  refusal: { label: 'В регламентах ответа нет', tone: 'warning' },
}

/** Renders «текст [1] текст» with clickable source markers. */
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
        className="mx-0.5 inline-grid h-[18px] min-w-[18px] cursor-pointer place-items-center rounded-sm border border-accent/30 bg-accent-soft px-1 align-[2px] text-[11px] leading-none font-semibold text-accent hover:bg-accent hover:text-accent-fg"
      >
        {n}
      </button>
    )
  })
}

export function Knowledge() {
  const { data: stats } = useKbStats()
  const { data: docs } = useKbDocuments()
  const { query } = useRoute()
  const [active, setActive] = useState<number | null>(1)
  const [question, setQuestion] = useState(query.get('q') ?? '')
  const [answer, setAnswer] = useState<KbAnswer | null>(null)
  const [loading, setLoading] = useState(false)
  const asked = useRef(false)
  const toast = useToast()
  const qc = useQueryClient()

  const ask = async (text: string) => {
    const q = text.trim()
    if (!q || loading) return
    setLoading(true)
    try {
      const resp = await askKb(q)
      setAnswer(resp)
      setActive(resp.sources.length > 0 ? 1 : null)
      qc.invalidateQueries({ queryKey: ['budget'] })
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Не удалось получить ответ', 'danger')
    } finally {
      setLoading(false)
    }
  }

  // A link from the copilot (?q=…) carries a question the visitor already asked: answer it once.
  useEffect(() => {
    const q = query.get('q')
    if (q && !asked.current) {
      asked.current = true
      void ask(q)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    void ask(question)
  }

  return (
    <>
      <PageHeader
        eyebrow="Модуль · Знания"
        title="Регламенты компании"
        description="Ответ собирается только из найденных разделов, у каждого утверждения есть ссылка на источник. Если в регламентах ответа нет, ассистент так и говорит."
      />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex min-w-0 flex-col gap-4">
          <div className="flex flex-col gap-2">
            <form
              onSubmit={submit}
              className="flex items-center gap-2 rounded-lg border border-line bg-surface p-1.5 pl-4 shadow-card focus-within:border-accent"
            >
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                maxLength={500}
                placeholder="Например: какая гарантия на монтаж?"
                className="h-9 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-faint"
              />
              <button
                type="submit"
                disabled={loading || !question.trim()}
                aria-label="Спросить"
                className="grid size-9 cursor-pointer place-items-center rounded-md bg-accent text-accent-fg disabled:opacity-50"
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
                  onClick={() => {
                    setQuestion(p.query)
                    void ask(p.query)
                  }}
                  className="cursor-pointer rounded-full border border-line bg-surface px-2.5 py-0.5 text-ink transition-colors hover:border-accent hover:text-accent"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {loading && !answer ? (
            <Skeleton className="h-56" />
          ) : !answer ? (
            <Card>
              <Empty
                title="Задайте вопрос по регламентам"
                text="Поиск идёт по 10 документам компании: цены и скидки, договоры, гарантия, рекламации, монтаж, склад, продажи, первичка, сервис, командировки."
              />
            </Card>
          ) : (
            <Card className={clsx(loading && 'opacity-60')}>
              <div className="text-sm font-medium text-muted">{answer.question}</div>
              <p className="mt-2 text-md leading-7 text-ink">{withCitations(answer.answer, setActive)}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Badge tone={MODE[answer.mode].tone} dot>
                  {MODE[answer.mode].label}
                </Badge>
                {answer.mode === 'model' && (
                  <span className="text-xs text-muted">
                    {answer.model.split('/').pop()} · {usd(answer.costUsd)}
                  </span>
                )}
              </div>
              {answer.note && <p className="mt-2 text-xs text-muted">{answer.note}</p>}
              {answer.sources.length > 0 && (
                <ul className="mt-4 flex flex-col gap-2 border-t border-line pt-4">
                  {answer.sources.map((s) => (
                    <li key={s.id}>
                      <button
                        onClick={() => setActive(s.id)}
                        className={clsx(
                          'w-full cursor-pointer rounded-md border px-3 py-2.5 text-left transition-colors',
                          active === s.id
                            ? 'border-accent bg-accent-soft/40'
                            : 'border-line hover:border-line-strong',
                        )}
                      >
                        <div className="flex flex-wrap items-center gap-x-2 text-sm font-medium text-ink">
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
                title="Проверка качества"
                hint="Эталонные вопросы прогоняются без модели: найден ли нужный раздел и есть ли отказ вне базы"
                icon={<ShieldCheck size={16} />}
              />
              <dl className="grid grid-cols-2 gap-3">
                <Metric label="Нужный раздел найден" value={`${stats.evalPassed} / ${stats.evalTotal}`} />
                <Metric label="Отказ вне базы" value={`${stats.refusalsCorrect} / ${stats.refusalsTotal}`} />
                <Metric label="Документов" value={String(stats.documents)} />
                <Metric label="Разделов" value={String(stats.chunks)} />
              </dl>
            </Card>
          )}
          <Card padded={false}>
            <div className="px-4 pt-4">
              <CardHeader
                title="Документы в базе"
                hint="Индекс SQLite FTS5 по основам слов, ранжирование BM25"
                icon={<BookOpen size={16} />}
              />
            </div>
            {!docs ? (
              <div className="p-4">
                <Skeleton className="h-40" />
              </div>
            ) : (
              <ul className="divide-y divide-line border-t border-line">
                {docs.map((d) => (
                  <li key={d.id} className="flex items-center gap-2.5 px-4 py-2.5 text-sm">
                    <FileText size={14} className="shrink-0 text-faint" />
                    <span className="flex-1 truncate text-ink-2">{d.title}</span>
                    <span className="num text-xs text-muted">
                      {count(d.chunks, ['раздел', 'раздела', 'разделов'])}
                    </span>
                  </li>
                ))}
              </ul>
            )}
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
