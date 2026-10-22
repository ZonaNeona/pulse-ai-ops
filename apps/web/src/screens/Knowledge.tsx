import { ArrowUp, BookOpen, FileText, ShieldCheck } from 'lucide-react'
import { Fragment, useState, type ReactNode } from 'react'
import { useKbAnswer, useKbStats } from '@/api/queries'
import { Badge, Card, CardHeader, PageHeader, PreviewBanner, Skeleton } from '@/ui/kit'

const DOCS = [
  ['Ценовая политика 2026', 14],
  ['Регламент согласования сделок', 9],
  ['Гарантийные обязательства', 11],
  ['Стандарт монтажа ВК и ОВ', 42],
  ['Работа с рекламациями', 8],
  ['Скрипты первого звонка', 6],
] as const

/** Renders «текст [1] текст» with superscript source markers. */
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
  const { data: answer } = useKbAnswer()
  const [active, setActive] = useState<number | null>(1)
  const [question, setQuestion] = useState('')
  return (
    <>
      <PageHeader
        eyebrow="Модуль · Знания"
        title="База знаний компании"
        description="Ответы только по регламентам: каждое утверждение со ссылкой на фрагмент. Нет источника — ассистент честно говорит «не знаю»."
      />
      <PreviewBanner what="поиск по регламентам компании и метрики качества подключаются." />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex min-w-0 flex-col gap-4">
          <form
            onSubmit={(e) => e.preventDefault()}
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
              aria-label="Спросить"
              className="grid size-9 place-items-center rounded-md bg-accent text-accent-fg"
            >
              <ArrowUp size={16} />
            </button>
          </form>

          {!answer ? (
            <Skeleton className="h-64" />
          ) : (
            <Card>
              <div className="text-sm text-muted">{answer.question}</div>
              <p className="mt-2 text-md leading-7 text-ink">{withCitations(answer.answer, setActive)}</p>
              <div className="mt-3 flex items-center gap-2">
                <Badge tone="success" dot>
                  Опирается на {answer.sources.length} источника
                </Badge>
              </div>
              <ul className="mt-4 flex flex-col gap-2 border-t border-line pt-4">
                {answer.sources.map((s) => (
                  <li key={s.id}>
                    <button
                      onClick={() => setActive(s.id)}
                      className={
                        'w-full rounded-md border px-3 py-2.5 text-left transition-colors ' +
                        (active === s.id ? 'border-accent bg-accent-soft/40' : 'border-line hover:border-line-strong')
                      }
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
            </Card>
          )}
        </div>

        <div className="flex flex-col gap-4">
          {!stats ? (
            <Skeleton className="h-48" />
          ) : (
            <Card>
              <CardHeader title="Качество ответов" hint="Прогон eval на эталонных вопросах" icon={<ShieldCheck size={16} />} />
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
              <CardHeader title="Документы в базе" hint={`${stats?.documents ?? '—'} документов, поиск BM25 + цитаты`} icon={<BookOpen size={16} />} />
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
