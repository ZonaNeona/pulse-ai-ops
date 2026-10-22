import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, Check, CircleDashed, FileUp, Loader2, X } from 'lucide-react'
import type { DocItem, DocStatus, GraphStep, StepStatus } from '@/api/types'
import { confirmDoc, rejectDoc, uploadDoc, useBudget, useDocs } from '@/api/queries'
import { navigate, useRoute, withQuery } from '@/app/router'
import { Meter } from '@/ui/charts'
import { ms, rub } from '@/ui/format'
import { Badge, Button, Card, CardHeader, Empty, Notice, PageHeader, Skeleton, type Tone } from '@/ui/kit'
import { useToast } from '@/ui/Toast'

const STATUS: Record<DocStatus, { label: string; tone: Tone }> = {
  mismatch: { label: 'Расхождение', tone: 'danger' },
  review: { label: 'Ждёт подтверждения', tone: 'warning' },
  recognized: { label: 'Распознан', tone: 'info' },
  posted: { label: 'Проведён', tone: 'success' },
}

export function Documents() {
  const { data } = useDocs()
  const { query } = useRoute()
  if (!data) return <Skeleton className="h-[600px]" />
  const selected = data.find((d) => String(d.id) === query.get('id')) ?? data[0]
  const waiting = data.filter((d) => d.status === 'mismatch' || d.status === 'review').length

  const handleUploaded = (created: DocItem) => {
    navigate(withQuery('/docs', { id: String(created.id) }), { replace: true })
  }

  return (
    <>
      <PageHeader
        eyebrow="Модуль · Документы"
        title="Входящие документы"
        description="Счета, договоры, УПД и акты проходят граф LangGraph: тип → поля → сверка с 1С и CRM → подтверждение человеком → проводка."
        actions={<Badge tone={waiting ? 'warning' : 'success'}>{waiting} ждут человека</Badge>}
      />
      <Notice tone="neutral" className="mb-4">
        <div className="flex w-full flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex size-2 shrink-0 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-semibold text-ink">LangGraph StateGraph:</span>
            <span className="text-muted">
              classify → extract → validate (1C/CRM) → review (human-in-the-loop) → draft (1C)
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-2 text-xs text-muted">
            <span>SQLite thread checkpoints</span>
            <span>•</span>
            <span>Сверка: 1С (ЗП-0388)</span>
          </div>
        </div>
      </Notice>
      <div className="grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
        <div className="flex flex-col gap-3">
          <Upload onUploaded={handleUploaded} />
          <Card padded={false}>
            {data.length === 0 ? (
              <Empty title="Документов нет" text="Загрузите первый файл выше" />
            ) : (
              <ul className="divide-y divide-line">
                {data.map((d) => (
                  <li key={d.id}>
                    <button
                      onClick={() => navigate(withQuery('/docs', { id: String(d.id) }), { replace: true })}
                      className={clsx(
                        'flex w-full items-start gap-3 px-3.5 py-3 text-left transition-colors',
                        selected && d.id === selected.id ? 'bg-accent-soft/60' : 'hover:bg-surface-2/60',
                      )}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 text-sm font-medium text-ink">
                          {d.kindLabel} {d.number}
                        </div>
                        <div className="mt-0.5 truncate text-xs text-muted">{d.counterparty}</div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <span className="num text-sm text-ink">{rub(d.amount)}</span>
                        <Badge tone={STATUS[d.status]?.tone ?? 'neutral'}>{STATUS[d.status]?.label ?? d.status}</Badge>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
        {selected ? (
          <DocDetail doc={selected} />
        ) : (
          <Card>
            <Empty title="Выберите документ" text="Слева в списке или загрузите свой" />
          </Card>
        )}
      </div>
    </>
  )
}

function Upload({ onUploaded }: { onUploaded?: (doc: DocItem) => void }) {
  const { data: budget } = useBudget()
  const toast = useToast()
  const queryClient = useQueryClient()
  const [uploading, setUploading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const isExhausted = budget ? budget.documentsLeft <= 0 : false

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const created = await uploadDoc(file)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['docs'] }),
        queryClient.invalidateQueries({ queryKey: ['budget'] }),
        queryClient.invalidateQueries({ queryKey: ['overview'] }),
      ])
      toast(`Документ «${created.kindLabel} ${created.number}» обработан в LangGraph`, 'success')
      onUploaded?.(created)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка обработки документа'
      toast(msg, 'danger')
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <label
      className={clsx(
        'flex flex-col items-center gap-1.5 rounded-lg border border-dashed border-line-strong bg-surface px-4 py-5 text-center transition-colors',
        uploading
          ? 'cursor-wait bg-surface-2/40 opacity-70'
          : isExhausted
            ? 'cursor-not-allowed opacity-60'
            : 'cursor-pointer hover:border-accent hover:bg-surface-2/30',
      )}
    >
      {uploading ? (
        <Loader2 size={18} className="animate-spin text-accent" />
      ) : (
        <FileUp size={18} className="text-muted" />
      )}
      <span className="text-sm font-medium text-ink">
        {uploading ? 'Обработка в LangGraph...' : 'Загрузите свой счёт или акт'}
      </span>
      <span className="text-xs text-muted">
        {uploading
          ? 'Распознавание → извлечение → сверка с 1С'
          : `PDF, фото или текст · осталось ${budget?.documentsLeft ?? '—'} из ${budget?.documentsCap ?? '—'} сегодня`}
      </span>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.txt"
        disabled={uploading || isExhausted}
        className="sr-only"
        onChange={handleFile}
      />
    </label>
  )
}

const STEP_ICON: Record<StepStatus, React.ReactNode> = {
  done: <Check size={13} />,
  active: <Loader2 size={13} className="animate-spin" />,
  waiting: <CircleDashed size={13} />,
  error: <X size={13} />,
  skipped: <CircleDashed size={13} />,
}
const STEP_TONE: Record<StepStatus, string> = {
  done: 'bg-success-soft text-success border-transparent',
  active: 'bg-warning-soft text-warning border-transparent',
  waiting: 'bg-surface text-faint border-line',
  error: 'bg-danger-soft text-danger border-transparent',
  skipped: 'bg-surface-2 text-faint border-line',
}

function Graph({ steps }: { steps: GraphStep[] }) {
  return (
    <ol className="grid gap-2 sm:grid-cols-5">
      {steps.map((s, i) => (
        <li key={s.node} className="relative">
          {i > 0 && <span className="absolute -left-2 top-3.5 hidden h-px w-2 bg-line-strong sm:block" />}
          <div className={clsx('flex h-full flex-col gap-1 rounded-md border p-2.5', STEP_TONE[s.status])}>
            <div className="flex items-center gap-1.5 text-xs font-medium">
              {STEP_ICON[s.status]}
              <span className="mono">{s.node}</span>
            </div>
            <div className="text-sm text-ink">{s.label}</div>
            <div className="text-xs text-muted">
              {s.note}
              {s.ms !== undefined && <span className="num"> · {ms(s.ms)}</span>}
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}

function DocDetail({ doc }: { doc: DocItem }) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [submitting, setSubmitting] = useState(false)
  const needsHuman = doc.status === 'mismatch' || doc.status === 'review'

  const handleConfirm = async () => {
    setSubmitting(true)
    try {
      await confirmDoc(doc.id)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['docs'] }),
        queryClient.invalidateQueries({ queryKey: ['overview'] }),
      ])
      toast(`Документ ${doc.number} подтверждён, черновик в 1С создан`, 'success')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка подтверждения'
      toast(msg, 'danger')
    } finally {
      setSubmitting(false)
    }
  }

  const handleReject = async () => {
    setSubmitting(true)
    try {
      await rejectDoc(doc.id)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['docs'] }),
        queryClient.invalidateQueries({ queryKey: ['overview'] }),
      ])
      toast('Поставщику отправлен запрос на исправление документа', 'neutral')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка отклонения'
      toast(msg, 'danger')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs text-muted">
              {doc.kindLabel} · получен {doc.receivedAgo}
            </div>
            <h2 className="mt-0.5 text-lg font-semibold tracking-[-0.01em] text-ink">
              {doc.kindLabel} {doc.number} от {doc.date}
            </h2>
            <div className="mt-0.5 text-sm text-muted">
              {doc.counterparty} · <span className="num text-ink">{rub(doc.amount)}</span>
            </div>
          </div>
          <Badge tone={STATUS[doc.status]?.tone ?? 'neutral'} dot>
            {STATUS[doc.status]?.label ?? doc.status}
          </Badge>
        </div>
        <div className="mt-4">
          <Graph steps={doc.steps} />
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card padded={false}>
          <div className="px-4 pt-4">
            <CardHeader title="Извлечённые поля" hint={`Средняя уверенность ${Math.round(doc.confidence * 100)}%`} />
          </div>
          {doc.fields.length === 0 ? (
            <Empty title="Поля скрыты" text="Документ проведён автоматически" />
          ) : (
            <table className="w-full border-t border-line text-sm">
              <tbody className="divide-y divide-line">
                {doc.fields.map((f) => (
                  <tr key={f.key} className={clsx(f.expected && 'bg-danger-soft/50')}>
                    <td className="w-36 px-4 py-2 text-muted">{f.label}</td>
                    <td className="px-2 py-2 text-ink">
                      {f.value}
                      {f.expected && <div className="text-xs text-danger">в заказе: {f.expected}</div>}
                    </td>
                    <td className="w-24 px-4 py-2">
                      <Meter value={f.confidence} max={1} tone={f.confidence >= 0.9 ? 'success' : 'warning'} />
                      <div className="num mt-0.5 text-right text-[11px] text-muted">{Math.round(f.confidence * 100)}%</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card>
          <CardHeader title="Сверка с 1С и CRM" hint="Правила проверки — код, а не модель" />
          {doc.checks.length === 0 ? (
            <Empty title="Проверок нет" />
          ) : (
            <ul className="flex flex-col gap-2.5">
              {doc.checks.map((c) => (
                <li key={c.label} className="flex gap-2.5 text-sm">
                  <span
                    className={clsx(
                      'mt-0.5 grid size-5 shrink-0 place-items-center rounded-full',
                      c.ok ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger',
                    )}
                  >
                    {c.ok ? <Check size={12} /> : <AlertTriangle size={11} />}
                  </span>
                  <div>
                    <div className="text-ink">{c.label}</div>
                    <div className="text-xs text-muted">{c.detail}</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {needsHuman ? (
            <div className="mt-5 flex flex-wrap gap-2 border-t border-line pt-4">
              <Button disabled={submitting} onClick={handleConfirm}>
                {submitting ? 'Проводка...' : 'Подтвердить и провести'}
              </Button>
              <Button disabled={submitting} variant="secondary" onClick={handleReject}>
                Запросить исправление
              </Button>
            </div>
          ) : doc.status === 'posted' ? (
            <div className="mt-5 flex items-center gap-2 border-t border-line pt-4 text-xs text-success">
              <Check size={14} />
              <span>Черновик проведён в 1С:Управление торговлей (документ закрыт)</span>
            </div>
          ) : null}
        </Card>
      </div>
    </div>
  )
}
