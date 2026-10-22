import clsx from 'clsx'
import { CornerDownLeft, Moon, Search, Sun } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { PRESETS } from '@/app/presets'
import { Kbd } from '@/ui/kit'
import { NAV } from './nav'
import { navigate, withQuery } from './router'
import { useTheme } from './theme'

type Command = {
  id: string
  label: string
  hint?: string
  group: string
  icon: React.ReactNode
  run: () => void
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState('')
  const [index, setIndex] = useState(0)
  const [theme, toggleTheme] = useTheme()
  const input = useRef<HTMLInputElement>(null)

  const commands = useMemo<Command[]>(
    () => [
      ...NAV.map((n) => ({
        id: n.path,
        label: n.label,
        hint: n.hint,
        group: 'Перейти',
        icon: <n.icon size={15} />,
        run: () => navigate(n.path),
      })),
      ...PRESETS.map((q) => ({
        id: q,
        label: q,
        group: 'Спросить копилота',
        icon: <Search size={15} />,
        run: () => navigate(withQuery('/copilot', { q })),
      })),
      {
        id: 'theme',
        label: theme === 'dark' ? 'Светлая тема' : 'Тёмная тема',
        group: 'Настройки',
        icon: theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />,
        run: toggleTheme,
      },
    ],
    [theme, toggleTheme],
  )

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? commands.filter((c) => (c.label + ' ' + (c.hint ?? '')).toLowerCase().includes(q)) : commands
  }, [commands, query])

  useEffect(() => {
    if (open) {
      setQuery('')
      setIndex(0)
      setTimeout(() => input.current?.focus(), 10)
    }
  }, [open])

  const choose = (c: Command | undefined) => {
    if (!c) return
    onClose()
    c.run()
  }

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setIndex((i) => Math.min(filtered.length - 1, i + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setIndex((i) => Math.max(0, i - 1))
    } else if (e.key === 'Enter') choose(filtered[index])
    else if (e.key === 'Escape') onClose()
  }

  let lastGroup = ''
  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh]">
          <motion.div
            className="absolute inset-0 bg-black/30 backdrop-blur-[1px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
          />
          <motion.div
            role="dialog"
            aria-label="Командная палитра"
            className="relative w-full max-w-[560px] overflow-hidden rounded-xl border border-line bg-surface shadow-pop"
            initial={{ opacity: 0, scale: 0.98, y: -6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="flex items-center gap-2.5 border-b border-line px-4">
              <Search size={16} className="text-muted" />
              <input
                ref={input}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setIndex(0)
                }}
                onKeyDown={onKey}
                placeholder="Перейти к экрану или спросить копилота…"
                className="h-12 flex-1 bg-transparent text-base outline-none placeholder:text-faint"
              />
              <Kbd>Esc</Kbd>
            </div>
            <div className="max-h-[360px] overflow-y-auto p-1.5">
              {filtered.length === 0 && (
                <div className="px-3 py-8 text-center text-sm text-muted">
                  Ничего не нашлось. Нажмите Enter, чтобы спросить копилота.
                </div>
              )}
              {filtered.map((c, i) => {
                const header = c.group !== lastGroup
                lastGroup = c.group
                return (
                  <div key={c.id}>
                    {header && (
                      <div className="px-2.5 pt-2 pb-1 text-xs font-medium text-faint">{c.group}</div>
                    )}
                    <button
                      onMouseMove={() => setIndex(i)}
                      onClick={() => choose(c)}
                      className={clsx(
                        'flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm',
                        i === index ? 'bg-surface-2 text-ink' : 'text-ink-2',
                      )}
                    >
                      <span className="text-muted">{c.icon}</span>
                      <span className="flex-1 truncate">{c.label}</span>
                      {i === index && <CornerDownLeft size={14} className="text-faint" />}
                    </button>
                  </div>
                )
              })}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
