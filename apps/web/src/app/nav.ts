import {
  Activity,
  BookOpen,
  Bot,
  Cable,
  Cpu,
  FileText,
  LayoutDashboard,
  Palette,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  path: string
  label: string
  icon: LucideIcon
  hint: string
  group: 'main' | 'ai' | 'meta'
  /** Module still being built: the screen shows its design on sample data. */
  soon?: boolean
}

export const NAV: NavItem[] = [
  { path: '/', label: 'Обзор', icon: LayoutDashboard, hint: 'Сводка по всем модулям и «Сделать сейчас»', group: 'main' },
  { path: '/sales', label: 'Продажи', icon: Activity, hint: 'Пульс отдела, команда, сделки, звонки', group: 'main' },
  { path: '/docs', label: 'Документы', icon: FileText, hint: 'Распознавание и сверка на LangGraph', group: 'main', soon: true },
  { path: '/knowledge', label: 'Знания', icon: BookOpen, hint: 'Ответы по регламентам с источниками', group: 'main', soon: true },
  { path: '/integrations', label: 'Интеграции', icon: Cable, hint: 'Битрикс24, 1С, Telegram, сверка', group: 'main' },
  { path: '/copilot', label: 'Копилот', icon: Bot, hint: 'Спросите своими словами — отвечает Hermes Agent', group: 'ai', soon: true },
  { path: '/under-the-hood', label: 'Под капотом', icon: Cpu, hint: 'Архитектура, трассировка агента, бюджет', group: 'ai' },
  { path: '/design', label: 'Дизайн-система', icon: Palette, hint: 'Токены и компоненты', group: 'meta' },
]

export const GITHUB_URL = 'https://github.com/'

export function activeNav(path: string): NavItem | undefined {
  if (path === '/') return NAV[0]
  return NAV.filter((n) => n.path !== '/').find((n) => path === n.path || path.startsWith(n.path + '/'))
}
