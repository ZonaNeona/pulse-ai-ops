import clsx from 'clsx'
import { ArrowUp, Bot, ChevronDown, Cpu, Link2, LoaderCircle } from 'lucide-react'
import { motion } from 'motion/react'
import { Fragment, useEffect, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { ChatDraft, ChatMessage } from '@/api/types'
import { api, useBudget, useChat } from '@/api/queries'
import { useRoute } from '@/app/router'
import { PRESETS } from '@/mock/demo'
import { ms, usd } from '@/ui/format'
import { Badge, Button, Card, PageHeader, PreviewBanner, Skeleton } from '@/ui/kit'
import { TraceTimeline } from '@/ui/Trace'

/** Minimal markdown: **bold** and line breaks — enough for agent answers, no HTML injection. */
function rich(text: string): ReactNode {
  return text.split('\n').map((line, i) => (
    <Fragment key={i}>
      {i > 0 && <br />}
      {line.split(/(\*\*[^*]+\*\*)/).map((p, j) =>
        p.startsWith('**') ? (
          <strong key={j} className="font-semibold text-ink">
            {p.slice(2, -2)}
          </strong>
        ) : (
          <Fragment key={j}>{p}</Fragment>
        ),
      )}
    </Fragment>
  ))
}

export function Copilot() {
  const { data: initialChat } = useChat()
  const { data: budget } = useBudget()
  const { query } = useRoute()
  const qc = useQueryClient()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [text, setText] = useState(query.get('q') ?? '')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (initialChat && messages.length === 0) {
      setMessages(initialChat)
    }
  }, [initialChat, messages.length])

  const send = async (msgText: string) => {
    const q = msgText.trim()
    if (!q || sending) return
    const userMsg: ChatMessage = {
      id: `u_${Date.now()}`,
      role: 'user',
      text: q,
    }
    setMessages((prev) => [...prev, userMsg])
    setText('')
    setSending(true)

    try {
      const res = await api<ChatMessage>('/copilot/chat', {
        method: 'POST',
        body: JSON.stringify({ message: q }),
      })
      setMessages((prev) => [...prev, res])
      qc.invalidateQueries({ queryKey: ['budget'] })
      qc.invalidateQueries({ queryKey: ['trace'] })
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Неизвестная ошибка'
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          role: 'assistant',
          text: `Не удалось получить ответ: ${errMsg}. Попробуйте ещё раз.`,
        },
      ])
    } finally {
      setSending(false)
    }
  }

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    send(text)
  }

  return (
    <>
      <PageHeader
        eyebrow="ИИ-слой · Hermes Agent"
        title="Копилот"
        description="Агент с инструментами поверх CRM, 1С, документов и базы знаний. Составные вопросы делит между подагентами, каждое число берёт из данных."
        actions={
          budget && (
            <Badge tone={budget.questionsLeft > 2 ? 'neutral' : 'warning'}>
              Осталось {budget.questionsLeft} из {budget.questionsCap} вопросов
            </Badge>
          )
        }
      />
      <div className="mx-auto flex max-w-[860px] flex-col gap-4">
        <PreviewBanner what="Hermes Agent с MCP-инструментами. Готовые пресеты отвечают из кэша мгновенно; произвольные запросы тарифицируются в пределах суточного лимита $1,5." />
        {messages.length === 0 ? (
          <Skeleton className="h-80" />
        ) : (
          messages.map((m, i) => (
            <motion.div key={m.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Message message={m} />
            </motion.div>
          ))
        )}

        {sending && (
          <div className="flex gap-3">
            <span className="mt-1 grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
              <Bot size={15} />
            </span>
            <div className="min-w-0 flex-1">
              <Card>
                <div className="flex items-center gap-2 text-sm text-muted">
                  <LoaderCircle size={15} className="animate-spin text-accent" />
                  <span>Hermes Agent анализирует данные и вызывает инструменты...</span>
                </div>
              </Card>
            </div>
          </div>
        )}

        <div className="sticky bottom-4 mt-2">
          <div className="no-scrollbar mb-2 flex gap-1.5 overflow-x-auto">
            {PRESETS.map((p) => (
              <button
                key={p}
                onClick={() => send(p)}
                className="h-7 shrink-0 rounded-full border border-line bg-surface px-3 text-xs text-ink-2 shadow-card transition-colors hover:border-line-strong hover:text-ink cursor-pointer"
              >
                {p}
              </button>
            ))}
          </div>
          <form
            onSubmit={onSubmit}
            className="flex items-end gap-2 rounded-xl border border-line bg-surface p-2 pl-4 shadow-pop focus-within:border-accent"
          >
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send(text)
                }
              }}
              rows={1}
              placeholder="Спросите о продажах, документах, оплатах или регламентах…"
              className="max-h-40 min-h-9 flex-1 resize-none bg-transparent py-2 text-base outline-none placeholder:text-faint"
            />
            <button
              type="submit"
              disabled={sending || !text.trim()}
              aria-label="Отправить"
              className="grid size-9 place-items-center rounded-lg bg-accent text-accent-fg disabled:opacity-40 cursor-pointer"
            >
              <ArrowUp size={16} />
            </button>
          </form>
          <p className="mt-1.5 text-center text-[11px] text-faint">
            Готовые вопросы отвечают из кэша мгновенно. Действия агента — только черновики с подтверждением.
          </p>
        </div>
      </div>
    </>
  )
}

function DraftCard({ draft }: { draft: ChatDraft }) {
  const [status, setStatus] = useState(draft.status)
  const [busy, setBusy] = useState(false)
  const qc = useQueryClient()

  const confirm = async () => {
    setBusy(true)
    try {
      await api(`/drafts/${draft.draft_id}/confirm`, { method: 'POST' })
      setStatus('confirmed')
      qc.invalidateQueries({ queryKey: ['overview'] })
      qc.invalidateQueries({ queryKey: ['deals'] })
    } finally {
      setBusy(false)
    }
  }

  const undo = async () => {
    setBusy(true)
    try {
      await api(`/drafts/${draft.draft_id}/undo`, { method: 'POST' })
      setStatus('undone')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-3 rounded-lg border border-line bg-surface-2/60 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-ink">Черновик действия (Human-in-the-loop)</span>
        <Badge tone={status === 'confirmed' ? 'success' : status === 'undone' ? 'neutral' : 'warning'}>
          {status === 'confirmed' ? 'Подтверждено в CRM' : status === 'undone' ? 'Отклонено' : 'Требуется подтверждение'}
        </Badge>
      </div>
      <div className="mt-2 text-sm text-ink-2">
        <strong>{draft.title}</strong>
        {draft.responsible && <div className="text-xs text-muted">Ответственный: {draft.responsible}</div>}
        {draft.deadline && <div className="text-xs text-muted">Срок: {draft.deadline}</div>}
      </div>
      {status === 'pending_confirmation' && (
        <div className="mt-3 flex items-center gap-2">
          <Button size="sm" variant="primary" loading={busy} onClick={confirm}>
            Подтвердить действие
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={undo}>
            Отклонить
          </Button>
        </div>
      )}
    </div>
  )
}

function Message({ message }: { message: ChatMessage }) {
  const [open, setOpen] = useState(true)
  if (message.role === 'user')
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-xl rounded-br-sm bg-accent px-4 py-2.5 text-base text-accent-fg">{message.text}</div>
      </div>
    )
  const run = message.trace
  return (
    <div className="flex gap-3">
      <span className="mt-1 grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
        <Bot size={15} />
      </span>
      <div className="min-w-0 flex-1">
        <Card>
          <div className="text-base leading-7 text-ink-2">{rich(message.text)}</div>
          {message.sources && (
            <div className="mt-3 flex flex-wrap gap-1.5 border-t border-line pt-3">
              {message.sources.map((s) => (
                <a
                  key={s.label}
                  href={s.href}
                  className="inline-flex h-6 items-center gap-1 rounded-sm bg-surface-2 px-2 text-xs text-ink-2 hover:text-ink"
                >
                  <Link2 size={12} />
                  {s.label}
                </a>
              ))}
            </div>
          )}
          {message.draft && <DraftCard draft={message.draft} />}
        </Card>
        {run && (
          <div className="mt-2 rounded-lg border border-line bg-surface/60">
            <button
              onClick={() => setOpen((o) => !o)}
              className="flex w-full items-center gap-2 px-3 py-2 text-xs text-muted hover:text-ink cursor-pointer"
            >
              <Cpu size={13} />
              <span className="flex-1 text-left">
                Ход агента: {run.steps.filter((s) => s.kind === 'tool').length} инструментов,{' '}
                {run.steps.filter((s) => s.kind === 'subagent').length} подагента · {ms(run.totalMs)} · {usd(run.costUsd)}
              </span>
              <ChevronDown size={14} className={clsx('transition-transform', open && 'rotate-180')} />
            </button>
            {open && (
              <div className="border-t border-line px-3 py-3">
                <TraceTimeline run={run} compact />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
