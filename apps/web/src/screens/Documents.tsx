import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, Check, ChevronDown, CircleDashed, FileUp, Loader2, X } from 'lucide-react'
import type { DocItem, DocStatus, GraphStep, StepStatus } from '@/api/types'
import { decideDoc, uploadDoc, useBudget, useDocs } from '@/api/queries'
import { navigate, useRoute, withQuery } from '@/app/router'
import { Meter } from '@/ui/charts'
import { ms, rub, usd } from '@/ui/format'
import { Badge, Button, Card, CardHeader, Empty, PageHeader, Skeleton, type Tone } from '@/ui/kit'
import { useToast } from '@/ui/Toast'

const STATUS: Record<DocStatus, { label: string; tone: Tone }> = {
  mismatch: { label: 'Расхождение', tone: 'danger' },
  review: { label: 'Ждёт решения', tone: 'warning' },
  processing: { label: 'В обработке', tone: 'info' },
  posted: { label: 'Проведён', tone: 'success' },
  rejected: { label: 'Отклонён', tone: 'neutral' },
  failed: { label: 'Не прочитан', tone: 'danger' },
}

const waiting = (d: DocItem) => d.status === 'mismatch' || d.status === 'review'

export function Documents() {
  const { data } = useDocs()
  const { query } = useRoute()
  if (!data) return <Skeleton className="h-[600px]" />
  const selected = data.find((d) => String(d.id) === query.get('id')) ?? data[0]
  const open = (id: number) => navigate(withQuery('/docs', { id: String(id) }), { replace: true })
  const pending = data.filter(waiting).length

  return (
    <>
      <PageHeader
        eyebrow="Модуль · Документы · LangGraph"
        title="Входящие документы"
        description="Каждый документ проходит граф: реквизиты → сверка с 1С, CRM и регламентами → решение человека, если что-то не так → проводка. Остановленный граф сохраняется в SQLite и продолжает работу после решения."
        actions={
          <Badge tone={pending ? 'warning' : 'success'}>
            {pending ? `${pending} ждут решения` : 'Всё проверено'}
          </Badge>
        }
      />
      <div className="grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
        <div className="flex flex-col gap-3">
          <Upload onUploaded={(doc) => open(doc.id)} />
          <Card padded={false}>
            {data.length === 0 ? (
              <Empty title="Документов нет" text="Загрузите свой файл выше" />
            ) : (
              <ul className="divide-y divide-line">
                {data.map((d) => (
                  <li key={d.id}>
                    <button
                      onClick={() => open(d.id)}
                      className={clsx(
                        'flex w-full cursor-pointer items-start gap-3 px-3.5 py-3 text-left transition-colors',
                        selected && d.id === selected.id ? 'bg-accent-soft/60' : 'hover:bg-surface-2/60',
                      )}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-ink">
                          {d.kindLabel} {d.number}
                        </div>
                        <div className="mt-0.5 truncate text-xs text-muted">
                          {d.counterparty}
                          {d.source === 'upload' && ' · ваш файл'}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <span className="num text-sm text-ink">{d.amount ? rub(d.amount) : '—'}</span>
                        <Badge tone={STATUS[d.status].tone}>{STATUS[d.status].label}</Badge>
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

function Upload({ onUploaded }: { onUploaded: (doc: DocItem) => void }) {
  const { data: budget } = useBudget()
  const toast = useToast()
  const qc = useQueryClient()
  const [uploading, setUploading] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const handle = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const created = await uploadDoc(file)
      await Promise.all(
        ['docs', 'budget', 'overview'].map((key) => qc.invalidateQueries({ queryKey: [key] })),
      )
      toast(
        `${created.kindLabel} ${created.number}: ${STATUS[created.status].label.toLowerCase()}`,
        'success',
      )
      onUploaded(created)
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Не удалось обработать файл', 'danger')
    } finally {
      setUploading(false)
      if (input.current) input.current.value = ''
    }
  }

  const model = budget?.modelConnected
  return (
    <label
      className={clsx(
        'flex flex-col items-center gap-1.5 rounded-lg border border-dashed border-line-strong bg-surface px-4 py-5 text-center transition-colors',
        uploading ? 'cursor-wait opacity-70' : 'cursor-pointer hover:border-accent hover:bg-surface-2/30',
      )}
    >
      {uploading ? (
        <Loader2 size={18} className="animate-spin text-accent" />
      ) : (
        <FileUp size={18} className="text-muted" />
      )}
      <span className="text-sm font-medium text-ink">
        {uploading ? 'Граф обрабатывает файл…' : 'Загрузите свой счёт, УПД или акт'}
      </span>
      <span className="text-xs text-muted">
        {model
          ? `PDF, TXT или фото · реквизиты читает модель, осталось ${budget?.documentsLeft ?? '—'} из ${budget?.documentsCap ?? '—'} сегодня`
          : 'PDF с текстом или TXT · модель сейчас не подключена, реквизиты читают правила'}
      </span>
      <input
        ref={input}
        type="file"
        accept={model ? '.pdf,.txt,.png,.jpg,.jpeg,.webp' : '.pdf,.txt'}
        disabled={uploading}
        className="sr-only"
        onChange={handle}
      />
    </label>
  )
}

const STEP_ICON: Record<StepStatus, React.ReactNode> = {
  done: <Check size={13} />,
  active: <CircleDashed size={13} />,
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
    <ol className="grid gap-2 sm:grid-cols-4">
      {steps.map((s) => (
        <li key={s.node} className={clsx('flex flex-col gap-1 rounded-md border p-2.5', STEP_TONE[s.status])}>
          <div className="flex items-center gap-1.5 text-xs font-medium">
            {STEP_ICON[s.status]}
            <span className="mono">{s.node}</span>
          </div>
          <div className="text-sm text-ink">{s.label}</div>
          <div className="text-xs text-muted">
            {s.note}
            {s.ms !== undefined && <span className="num"> · {ms(s.ms)}</span>}
          </div>
        </li>
      ))}
    </ol>
  )
}

function DocDetail({ doc }: { doc: DocItem }) {
  const toast = useToast()
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [showText, setShowText] = useState(false)

  const decide = async (approve: boolean) => {
    setBusy(true)
    try {
      const updated = await decideDoc(doc.id, approve)
      navigate(withQuery('/docs', { id: String(doc.id) }), { replace: true }) // keep it open after the list re-sorts
      await Promise.all(['docs', 'overview'].map((key) => qc.invalidateQueries({ queryKey: [key] })))
      toast(updated.decision, approve ? 'success' : 'neutral')
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить решение', 'danger')
    } finally {
      setBusy(false)
    }
  }

  const engine =
    doc.engine === 'model'
      ? `Реквизиты прочитала модель ${doc.model.split('/').pop()} · ${usd(doc.costUsd)}`
      : 'Реквизиты прочитаны правилами, без модели'

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs text-muted">
              {doc.source === 'upload' ? 'Ваш файл' : 'Поступил'} · {doc.receivedAgo}
            </div>
            <h2 className="mt-0.5 text-lg font-semibold tracking-[-0.01em] text-ink">
              {doc.kindLabel} {doc.number}
              {doc.date && ` от ${doc.date}`}
            </h2>
            <div className="mt-0.5 text-sm text-muted">
              {doc.counterparty} ·{' '}
              <span className="num text-ink">{doc.amount ? rub(doc.amount) : 'сумма не найдена'}</span>
            </div>
          </div>
          <Badge tone={STATUS[doc.status].tone} dot>
            {STATUS[doc.status].label}
          </Badge>
        </div>
        <div className="mt-4">
          <Graph steps={doc.steps} />
        </div>
        <div className="mt-3 text-xs text-muted">{engine}</div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card padded={false}>
          <div className="px-4 pt-4">
            <CardHeader title="Реквизиты" hint="Красным — расхождение с данными 1С" />
          </div>
          {doc.fields.length === 0 ? (
            <Empty title="Реквизиты не прочитаны" text={doc.decision || 'Документ не удалось разобрать'} />
          ) : (
            <table className="w-full border-t border-line text-sm">
              <tbody className="divide-y divide-line">
                {doc.fields.map((f) => (
                  <tr key={f.key} className={clsx(f.expected && 'bg-danger-soft/50')}>
                    <td className="w-32 px-4 py-2 text-muted">{f.label}</td>
                    <td className={clsx('px-2 py-2', f.confidence === 0 ? 'text-faint' : 'text-ink')}>
                      {f.value}
                      {f.expected && <div className="text-xs text-danger">в заказе 1С: {f.expected}</div>}
                    </td>
                    <td className="w-24 px-4 py-2">
                      <Meter
                        value={f.confidence}
                        max={1}
                        tone={f.confidence >= 0.9 ? 'success' : 'warning'}
                      />
                      <div className="num mt-0.5 text-right text-[11px] text-muted">
                        {Math.round(f.confidence * 100)}%
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card>
          <CardHeader title="Проверки" hint="Код по данным 1С, CRM и регламентам — не модель" />
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
                  <div className="min-w-0">
                    <div className="text-ink">{c.label}</div>
                    <div className="text-xs text-muted">{c.detail}</div>
                    {c.rule && <div className="mt-0.5 text-[11px] text-accent">{c.rule}</div>}
                  </div>
                </li>
              ))}
            </ul>
          )}
          {waiting(doc) ? (
            <div className="mt-5 border-t border-line pt-4">
              <p className="mb-3 text-xs text-muted">Граф остановлен и ждёт вашего решения.</p>
              <div className="flex flex-wrap gap-2">
                <Button disabled={busy} onClick={() => decide(true)}>
                  {busy ? 'Сохраняю…' : 'Провести'}
                </Button>
                <Button disabled={busy} variant="secondary" onClick={() => decide(false)}>
                  Отклонить
                </Button>
              </div>
            </div>
          ) : doc.decision ? (
            <div className="mt-5 flex items-start gap-2 border-t border-line pt-4 text-xs text-muted">
              <Check size={14} className="mt-px shrink-0 text-success" />
              <span>
                {doc.decision}
                {doc.status === 'posted' &&
                  '. В демо 1С только читается: проводка остаётся черновиком на стенде.'}
              </span>
            </div>
          ) : null}
        </Card>
      </div>

      {doc.text && (
        <Card padded={false}>
          <button
            onClick={() => setShowText((v) => !v)}
            className="flex w-full cursor-pointer items-center justify-between px-4 py-3 text-sm font-medium text-ink"
          >
            Текст документа, который читал граф
            <ChevronDown
              size={16}
              className={clsx('text-muted transition-transform', showText && 'rotate-180')}
            />
          </button>
          {showText && (
            <pre className="mono max-h-80 overflow-auto border-t border-line px-4 py-3 text-xs leading-5 whitespace-pre-wrap text-ink-2">
              {doc.text}
            </pre>
          )}
        </Card>
      )}
    </div>
  )
}
