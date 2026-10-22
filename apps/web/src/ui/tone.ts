export type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info'

export const toneText: Record<Tone, string> = {
  neutral: 'text-ink',
  accent: 'text-accent',
  success: 'text-success',
  warning: 'text-warning',
  danger: 'text-danger',
  info: 'text-info',
}

export const toneSoft: Record<Tone, string> = {
  neutral: 'bg-surface-2 text-ink-2',
  accent: 'bg-accent-soft text-accent',
  success: 'bg-success-soft text-success',
  warning: 'bg-warning-soft text-warning',
  danger: 'bg-danger-soft text-danger',
  info: 'bg-info-soft text-info',
}

export const toneBg: Record<Tone, string> = {
  neutral: 'bg-faint',
  accent: 'bg-accent',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
  info: 'bg-info',
}
