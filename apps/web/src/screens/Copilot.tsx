import clsx from 'clsx'
import { ArrowUp, Bot, ChevronDown, Cpu, Link2 } from 'lucide-react'
import { motion } from 'motion/react'
import { Fragment, useState, type ReactNode } from 'react'
import type { ChatMessage } from '@/api/types'
import { useBudget, useChat } from '@/api/queries'
import { useRoute } from '@/app/router'
import { PRESETS } from '@/mock/demo'
import { ms, usd } from '@/ui/format'
import { Badge, Card, PageHeader, PreviewBanner, Skeleton } from '@/ui/kit'
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
  const { data: chat } = useChat()
  const { data: budget } = useBudget()
  const { query } = useRoute()
  const [text, setText] = useState(query.get('q') ?? '')
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
        <PreviewBanner what="ответ и ход агента ниже — пример. Живой Hermes Agent подключается." />
        {!chat ? (
          <Skeleton className="h-80" />
        ) : (
          chat.map((m, i) => (
            <motion.div key={m.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Message message={m} />
            </motion.div>
          ))
        )}

        <div className="sticky bottom-4 mt-2">
          <div className="no-scrollbar mb-2 flex gap-1.5 overflow-x-auto">
            {PRESETS.map((p) => (
              <button
                key={p}
                onClick={() => setText(p)}
                className="h-7 shrink-0 rounded-full border border-line bg-surface px-3 text-xs text-ink-2 shadow-card transition-colors hover:border-line-strong hover:text-ink"
              >
                {p}
              </button>
            ))}
          </div>
          <form
            onSubmit={(e) => e.preventDefault()}
            className="flex items-end gap-2 rounded-xl border border-line bg-surface p-2 pl-4 shadow-pop focus-within:border-accent"
          >
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={1}
              placeholder="Спросите о продажах, документах, оплатах или регламентах…"
              className="max-h-40 min-h-9 flex-1 resize-none bg-transparent py-2 text-base outline-none placeholder:text-faint"
            />
            <button type="submit" aria-label="Отправить" className="grid size-9 place-items-center rounded-lg bg-accent text-accent-fg">
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
        </Card>
        {run && (
          <div className="mt-2 rounded-lg border border-line bg-surface/60">
            <button
              onClick={() => setOpen((o) => !o)}
              className="flex w-full items-center gap-2 px-3 py-2 text-xs text-muted hover:text-ink"
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
