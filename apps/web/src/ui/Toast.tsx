import clsx from 'clsx'
import { CheckCircle2, AlertCircle, Info } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

type ToastTone = 'neutral' | 'success' | 'danger'
type ToastItem = { id: number; text: string; tone: ToastTone }

const ToastContext = createContext<(text: string, tone?: ToastTone) => void>(() => {})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const push = useCallback((text: string, tone: ToastTone = 'neutral') => {
    const id = Date.now() + Math.random()
    setItems((list) => [...list.slice(-2), { id, text, tone }])
    setTimeout(() => setItems((list) => list.filter((x) => x.id !== id)), tone === 'danger' ? 6000 : 3500)
  }, [])
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-[min(380px,calc(100vw-32px))] flex-col gap-2">
        <AnimatePresence>
          {items.map((t) => (
            <motion.div
              key={t.id}
              role="status"
              initial={{ opacity: 0, y: 8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 4 }}
              transition={{ duration: 0.2 }}
              className="pointer-events-auto flex items-start gap-2 rounded-lg border border-line bg-surface px-3.5 py-3 text-sm text-ink shadow-pop"
            >
              <span
                className={clsx(
                  'mt-px',
                  t.tone === 'success' ? 'text-success' : t.tone === 'danger' ? 'text-danger' : 'text-accent',
                )}
              >
                {t.tone === 'success' ? (
                  <CheckCircle2 size={16} />
                ) : t.tone === 'danger' ? (
                  <AlertCircle size={16} />
                ) : (
                  <Info size={16} />
                )}
              </span>
              {t.text}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useToast = () => useContext(ToastContext)
