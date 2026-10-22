import clsx from 'clsx'
import { AlertCircle, ArrowDownRight, ArrowUpRight, Info, LoaderCircle, RefreshCw } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { initials } from './format'
import { toneBg, toneSoft, type Tone } from './tone'

export type { Tone }

export function Card({
  children,
  className,
  padded = true,
  interactive,
  onClick,
}: {
  children: ReactNode
  className?: string
  padded?: boolean
  interactive?: boolean
  onClick?: () => void
}) {
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag
      onClick={onClick}
      className={clsx(
        'block w-full rounded-lg border border-line bg-surface text-left shadow-card',
        padded && 'p-4',
        (interactive || onClick) && 'transition-colors duration-150 hover:border-line-strong',
        className,
      )}
    >
      {children}
    </Tag>
  )
}

export function CardHeader({
  title,
  hint,
  action,
  icon,
  className,
}: {
  title: ReactNode
  hint?: ReactNode
  action?: ReactNode
  icon?: ReactNode
  className?: string
}) {
  return (
    <div className={clsx('mb-3 flex items-start justify-between gap-3', className)}>
      <div className="flex min-w-0 items-start gap-2">
        {icon && <span className="mt-0.5 text-muted">{icon}</span>}
        <div className="min-w-0">
          <h3 className="text-base font-semibold tracking-[-0.01em] text-ink">{title}</h3>
          {hint && <p className="mt-0.5 text-sm text-muted">{hint}</p>}
        </div>
      </div>
      {action}
    </div>
  )
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  eyebrow?: ReactNode
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-xs font-medium text-muted">{eyebrow}</div>}
        <h1 className="text-xl font-semibold tracking-[-0.02em] text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  )
}

export function Badge({
  tone = 'neutral',
  children,
  className,
  dot,
}: {
  tone?: Tone
  children: ReactNode
  className?: string
  dot?: boolean
}) {
  return (
    <span
      className={clsx(
        'inline-flex h-5 items-center gap-1 rounded-sm px-1.5 text-xs font-medium whitespace-nowrap',
        toneSoft[tone],
        className,
      )}
    >
      {dot && <span className={clsx('size-1.5 rounded-full', toneBg[tone])} />}
      {children}
    </span>
  )
}

export function Dot({ tone = 'neutral', pulse, className }: { tone?: Tone; pulse?: boolean; className?: string }) {
  return (
    <span className={clsx('relative inline-flex size-2 shrink-0', className)}>
      {pulse && <span className={clsx('absolute inset-0 animate-ping rounded-full opacity-50', toneBg[tone])} />}
      <span className={clsx('relative size-2 rounded-full', toneBg[tone])} />
    </span>
  )
}

/** Change vs. previous period. `invert` — growth is bad (missed calls, overdue). */
export function Delta({ value, suffix = '%', invert }: { value: number | null; suffix?: string; invert?: boolean }) {
  if (value === null) return null
  const flat = value === 0
  const good = flat ? null : invert ? value < 0 : value > 0
  return (
    <span
      className={clsx(
        'num inline-flex h-5 items-center gap-0.5 rounded-sm px-1 text-xs font-medium',
        good === null ? 'bg-surface-2 text-muted' : good ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger',
      )}
    >
      {!flat && (value > 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />)}
      {Math.abs(value)}
      {suffix}
    </span>
  )
}

type ButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> & {
  children?: ReactNode
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  icon?: ReactNode
  loading?: boolean
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  loading,
  disabled,
  className,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={clsx(
        'inline-flex shrink-0 items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap transition-colors duration-150 disabled:opacity-50',
        size === 'sm' ? 'h-7 px-2.5 text-sm' : 'h-8 px-3 text-sm',
        variant === 'primary' && 'bg-accent text-accent-fg hover:bg-accent-2',
        variant === 'secondary' && 'border border-line bg-surface text-ink shadow-card hover:bg-surface-2',
        variant === 'ghost' && 'text-ink-2 hover:bg-surface-2 hover:text-ink',
        variant === 'danger' && 'bg-danger-soft text-danger hover:brightness-95',
        className,
      )}
      {...rest}
    >
      {loading ? <LoaderCircle size={14} className="animate-spin" /> : icon}
      {children}
    </button>
  )
}

export function IconButton({
  label,
  children,
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={clsx(
        'grid size-8 shrink-0 place-items-center rounded-md text-muted transition-colors hover:bg-surface-2 hover:text-ink',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  className,
}: {
  options: { id: T; label: ReactNode }[]
  value: T
  onChange: (v: T) => void
  className?: string
}) {
  return (
    <div role="tablist" className={clsx('inline-flex rounded-md bg-surface-2 p-0.5', className)}>
      {options.map((o) => (
        <button
          key={o.id}
          role="tab"
          aria-selected={o.id === value}
          onClick={() => onChange(o.id)}
          className={clsx(
            'h-7 rounded-[5px] px-2.5 text-sm font-medium whitespace-nowrap transition-colors duration-150',
            o.id === value ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

const hues = [250, 170, 25, 300, 200, 45, 330, 120]
export function Avatar({ name, size = 28, seed }: { name: string; size?: number; seed?: number }) {
  const hue = hues[(seed ?? name.length) % hues.length]
  return (
    <span
      className="inline-grid shrink-0 place-items-center rounded-full font-semibold"
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.38),
        background: `hsl(${hue} 70% 55% / .16)`,
        color: `color-mix(in oklab, hsl(${hue} 55% 42%) 70%, var(--text))`,
      }}
      aria-hidden
    >
      {initials(name)}
    </span>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="mono inline-flex h-5 min-w-5 items-center justify-center rounded-sm border border-line bg-surface-2 px-1 text-[11px] text-muted">
      {children}
    </kbd>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('skeleton rounded-md', className)} />
}

export function Empty({
  icon,
  title,
  text,
  action,
}: {
  icon?: ReactNode
  title: string
  text?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center px-6 py-10 text-center">
      {icon && <div className="mb-3 grid size-10 place-items-center rounded-lg bg-surface-2 text-muted">{icon}</div>}
      <p className="text-base font-medium text-ink">{title}</p>
      {text && <p className="mt-1 max-w-sm text-sm text-muted">{text}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <Empty
      icon={<AlertCircle size={20} />}
      title="Не удалось загрузить"
      text={error instanceof Error ? error.message : 'Ошибка запроса'}
      action={
        retry && (
          <Button variant="secondary" icon={<RefreshCw size={14} />} onClick={retry}>
            Повторить
          </Button>
        )
      }
    />
  )
}

export function Notice({
  tone = 'info',
  children,
  icon,
  action,
  className,
}: {
  tone?: Tone
  children: ReactNode
  icon?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={clsx('flex items-start gap-2.5 rounded-md px-3 py-2.5 text-sm', toneSoft[tone], className)}>
      <span className="mt-px shrink-0">{icon ?? <Info size={15} />}</span>
      <div className="min-w-0 flex-1">{children}</div>
      {action}
    </div>
  )
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={clsx(
        'relative h-5 w-9 shrink-0 rounded-full transition-colors duration-150 disabled:opacity-50',
        checked ? 'bg-accent' : 'bg-surface-3',
      )}
    >
      <span
        className={clsx(
          'absolute top-0.5 size-4 rounded-full bg-white shadow transition-all duration-150',
          checked ? 'left-[18px]' : 'left-0.5',
        )}
      />
    </button>
  )
}

/** Labelled value in a definition grid: «Сумма — 412 300 ₽». */
export function Field({ label, children, className }: { label: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={clsx('min-w-0', className)}>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-0.5 truncate text-sm text-ink">{children}</dd>
    </div>
  )
}

/** Shown on screens whose module is still being built: what you see is the design on sample data. */
export function PreviewBanner({ what }: { what: string }) {
  return (
    <Notice tone="accent" className="mb-4">
      <span className="font-medium">Модуль подключается.</span> Сейчас показан дизайн экрана на примерах: {what}
    </Notice>
  )
}
