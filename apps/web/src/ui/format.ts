import type { Kpi } from '@/api/types'

const nf = new Intl.NumberFormat('ru-RU')
const rubFmt = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 })
export const num = (v: number) => nf.format(v)
export const rub = (v: number) => rubFmt.format(v)
/** $0,0061 for per-call costs, $0,42 for totals. */
export const usd = (v: number) => '$' + v.toFixed(v > 0 && v < 0.1 ? 4 : 2).replace('.', ',')

/** 1 250 000 → «1,25 млн ₽», 21 840 000 → «21,8 млн ₽», 84 000 → «84 тыс. ₽». */
export function rubShort(v: number): string {
  const a = Math.abs(v)
  if (a >= 1_000_000)
    return `${(v / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: a >= 10_000_000 ? 1 : 2 })} млн ₽`
  if (a >= 10_000) return `${Math.round(v / 1000).toLocaleString('ru-RU')} тыс. ₽`
  return rub(v)
}

/** plural(5, ['звонок', 'звонка', 'звонков']) → «звонков». */
export function plural(n: number, forms: [string, string, string]): string {
  const m10 = n % 10
  const m100 = n % 100
  if (m10 === 1 && m100 !== 11) return forms[0]
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return forms[1]
  return forms[2]
}

export const count = (n: number, forms: [string, string, string]) => `${num(n)} ${plural(n, forms)}`

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('')
}

export function duration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

export function ms(v: number): string {
  return v >= 1000 ? `${(v / 1000).toFixed(1)} с` : `${Math.round(v)} мс`
}

export function formatKpi(kpi: Kpi): string {
  if (kpi.value === null) return '—'
  switch (kpi.unit) {
    case 'rub':
      return rubShort(kpi.value)
    case 'pct':
      return `${num(kpi.value)}%`
    case 'min':
      return `${num(kpi.value)} мин`
    case 'sec':
      return `${num(kpi.value)} с`
    default:
      return num(kpi.value)
  }
}

export function ago(minutes: number): string {
  if (minutes < 1) return 'только что'
  if (minutes < 60) return `${minutes} мин назад`
  const h = Math.floor(minutes / 60)
  if (h < 24) return `${h} ${plural(h, ['час', 'часа', 'часов'])} назад`
  const d = Math.floor(h / 24)
  return `${d} ${plural(d, ['день', 'дня', 'дней'])} назад`
}
