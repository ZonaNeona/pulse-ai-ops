import clsx from 'clsx'
import { ArrowUp, Bot, ChevronDown, Cpu, Link2, LoaderCircle } from 'lucide-react'
import { motion } from 'motion/react'
import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { ChatDraft, ChatMessage, Engine } from '@/api/types'
import { askCopilot, decideDraft, useBudget } from '@/api/queries'
import { PRESETS } from '@/app/presets'
import { navigate, useRoute } from '@/app/router'
import { ms, usd } from '@/ui/format'
import { Badge, Button, Card, PageHeader, type Tone } from '@/ui/kit'
import { TraceTimeline } from '@/ui/Trace'

const ENGINE: Record<Engine, { label: string; tone: Tone }> = {
  rules: { label: 'Готовый ответ из инструментов · без модели', tone: 'neutral' },
  kb: { label: 'Ответ по регламентам', tone: 'info' },
  model: { label: 'Агент с инструментами', tone: 'accent' },
  hermes: { label: 'Hermes Agent', tone: 'accent' },
  none: { label: 'Модель недоступна', tone: 'warning' },
}

const INTRO: ChatMessage = {
  id: 'intro',
  role: 'assistant',
  text:
    'Я отвечаю по данным стенда: CRM, 1С, входящие документы и регламенты компании. ' +
    'Частые вопросы — кнопки внизу — считаются сразу из инструментов, без модели. ' +
    'Свободный вопрос разбирает агент: сам выбирает инструменты, а под ответом виден его ход и стоимость.',
}

/** Minimal markdown: **bold**, _italic_ notes and line breaks — no HTML from the model reaches the page. */
function rich(text: string): ReactNode {
  return text.split('\n').map((line, i) => (
    <Fragment key={i}>
      {i > 0 && <br />}
      {line.split(/(\*\*[^*]+\*\*)/).map((p, j) =>
        p.startsWith('**') && p.endsWith('**') ? (
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
  const { data: budget } = useBudget()
  const { query } = useRoute()
  const qc = useQueryClient()
  const [messages, setMessages] = useState<ChatMessage[]>([INTRO])
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const bottom = useRef<HTMLDivElement>(null)
  const started = useRef(false)

  const send = async (raw: string) => {
    const q = raw.trim()
    if (!q || sending) return
    setMessages((prev) => [...prev, { id: `u_${Date.now()}`, role: 'user', text: q }])
    setText('')
    setSending(true)
    try {
      const answer = await askCopilot(q)
      setMessages((prev) => [...prev, answer])
      ;['budget', 'trace', 'overview'].forEach((key) => qc.invalidateQueries({ queryKey: [key] }))
    } catch (err: unknown) {
      const reason = err instanceof Error ? err.message : 'нет связи с сервером'
      setMessages((prev) => [
        ...prev,
        { id: `e_${Date.now()}`, role: 'assistant', text: `Не получилось ответить: ${reason}.` },
      ])
    } finally {
      setSending(false)
    }
  }

  // ?q=… from the overview or ⌘K: ask it once on arrival.
  useEffect(() => {
    const q = query.get('q')
    if (q && !started.current) {
      started.current = true
      void send(q)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, sending])

  const free = budget?.modelConnected
  return (
    <>
      <PageHeader
        eyebrow="ИИ-слой · агент с инструментами"
        title="Копилот"
        description="Спросите своими словами о продажах, оплатах, документах или правилах компании. Каждое число в ответе взято из инструмента, а не придумано моделью."
        actions={
          budget &&
          (free ? (
            <Badge tone={budget.questionsLeft > 2 ? 'neutral' : 'warning'}>
              Свободных вопросов: {budget.questionsLeft} из {budget.questionsCap}
            </Badge>
          ) : (
            <Badge tone="warning">Модель не подключена — работают готовые вопросы</Badge>
          ))
        }
      />
      <div className="mx-auto flex max-w-[860px] flex-col gap-4">
        {messages.map((m) => (
          <motion.div
            key={m.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
          >
            <Message message={m} />
          </motion.div>
        ))}

        {sending && (
          <div className="flex gap-3">
            <span className="mt-1 grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
              <Bot size={15} />
            </span>
            <Card className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-sm text-muted">
                <LoaderCircle size={15} className="animate-spin text-accent" />
                Собираю данные из инструментов…
              </div>
            </Card>
          </div>
        )}
        <div ref={bottom} />

        <div className="sticky bottom-4 mt-2">
          <div className="no-scrollbar mb-2 flex gap-1.5 overflow-x-auto">
            {PRESETS.map((p) => (
              <button
                key={p}
                onClick={() => send(p)}
                disabled={sending}
                className="h-7 shrink-0 cursor-pointer rounded-full border border-line bg-surface px-3 text-xs text-ink-2 shadow-card transition-colors hover:border-line-strong hover:text-ink disabled:opacity-50"
              >
                {p}
              </button>
            ))}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              void send(text)
            }}
            className="flex items-end gap-2 rounded-xl border border-line bg-surface p-2 pl-4 shadow-pop focus-within:border-accent"
          >
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  void send(text)
                }
              }}
              rows={1}
              maxLength={800}
              placeholder="Спросите своими словами…"
              className="max-h-40 min-h-9 flex-1 resize-none bg-transparent py-2 text-base outline-none placeholder:text-faint"
            />
            <button
              type="submit"
              disabled={sending || !text.trim()}
              aria-label="Отправить"
              className="grid size-9 cursor-pointer place-items-center rounded-lg bg-accent text-accent-fg disabled:opacity-40"
            >
              <ArrowUp size={16} />
            </button>
          </form>
          <p className="mt-1.5 text-center text-[11px] text-faint">
            Агент только читает данные. Действия — черновики, которые подтверждаете вы. Бюджет стенда на
            модель — $1,5 в сутки.
          </p>
        </div>
      </div>
    </>
  )
}

function DraftCard({ draft }: { draft: ChatDraft }) {
  const [status, setStatus] = useState(draft.status)
  const [busy, setBusy] = useState(false)

  const decide = async (confirm: boolean) => {
    setBusy(true)
    try {
      const res = await decideDraft(draft.draft_id, confirm)
      setStatus(res.status as ChatDraft['status'])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-3 rounded-lg border border-line bg-surface-2/60 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-ink">Черновик задачи</span>
        <Badge tone={status === 'confirmed' ? 'success' : status === 'discarded' ? 'neutral' : 'warning'}>
          {status === 'confirmed'
            ? 'Подтверждён'
            : status === 'discarded'
              ? 'Отклонён'
              : 'Ждёт вашего решения'}
        </Badge>
      </div>
      <div className="mt-2 text-sm text-ink-2">
        <strong>{draft.title}</strong>
        <div className="text-xs text-muted">
          {draft.responsible && `Ответственный: ${draft.responsible}`}
          {draft.deadline && ` · срок ${draft.deadline.split('-').reverse().join('.')}`}
        </div>
      </div>
      {status === 'pending' ? (
        <div className="mt-3 flex items-center gap-2">
          <Button size="sm" loading={busy} onClick={() => decide(true)}>
            Подтвердить
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => decide(false)}>
            Отклонить
          </Button>
        </div>
      ) : (
        status === 'confirmed' && (
          <p className="mt-2 text-xs text-muted">
            В демо задача сохранена только для вас — во внешние системы ничего не ушло.
          </p>
        )
      )}
    </div>
  )
}

function Message({ message }: { message: ChatMessage }) {
  const [open, setOpen] = useState(message.engine === 'model' || message.engine === 'hermes')
  if (message.role === 'user')
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-xl rounded-br-sm bg-accent px-4 py-2.5 text-base text-accent-fg">
          {message.text}
        </div>
      </div>
    )
  const run = message.trace
  const tools = run?.steps.filter((s) => s.kind === 'tool').length ?? 0
  return (
    <div className="flex gap-3">
      <span className="mt-1 grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
        <Bot size={15} />
      </span>
      <div className="min-w-0 flex-1">
        <Card>
          {message.engine && (
            <div className="mb-2">
              <Badge tone={ENGINE[message.engine].tone}>
                {ENGINE[message.engine].label}
                {run?.model && ` · ${run.model.split('/').pop()}`}
              </Badge>
            </div>
          )}
          <div className="text-base leading-relaxed text-ink-2">{rich(message.text)}</div>
          {message.sources && message.sources.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5 border-t border-line pt-3">
              {message.sources.map((s) => (
                <button
                  key={s.label}
                  onClick={() => navigate(s.href)}
                  className="inline-flex h-6 cursor-pointer items-center gap-1 rounded-sm bg-surface-2 px-2 text-xs text-ink-2 hover:text-ink"
                >
                  <Link2 size={12} />
                  {s.label}
                </button>
              ))}
            </div>
          )}
          {message.drafts?.map((d) => (
            <DraftCard key={d.draft_id} draft={d} />
          ))}
        </Card>
        {run && (
          <div className="mt-2 rounded-lg border border-line bg-surface/60">
            <button
              onClick={() => setOpen((o) => !o)}
              className="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-xs text-muted hover:text-ink"
            >
              <Cpu size={13} />
              <span className="flex-1 text-left">
                Ход: {tools}{' '}
                {tools === 1 ? 'инструмент' : tools > 1 && tools < 5 ? 'инструмента' : 'инструментов'} ·{' '}
                {ms(run.totalMs)} · {run.costUsd ? usd(run.costUsd) : 'бесплатно'}
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
