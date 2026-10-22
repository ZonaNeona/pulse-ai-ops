import {
  Activity,
  BookOpen,
  CalendarRange,
  Bot,
  Cable,
  Cpu,
  FileText,
  LayoutDashboard,
  Palette,
  Route,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  path: string
  label: string
  icon: LucideIcon
  hint: string
  group: 'main' | 'ai' | 'work'
  /** Module still being built: the screen shows its design on sample data. */
  soon?: boolean
}

export const NAV: NavItem[] = [
  {
    path: '/',
    label: 'Обзор',
    icon: LayoutDashboard,
    hint: 'Сводка по всем модулям и «Сделать сейчас»',
    group: 'main',
  },
  {
    path: '/sales',
    label: 'Продажи',
    icon: Activity,
    hint: 'Пульс отдела, команда, сделки, звонки',
    group: 'main',
  },
  {
    path: '/docs',
    label: 'Документы',
    icon: FileText,
    hint: 'Распознавание и сверка на LangGraph',
    group: 'main',
  },
  {
    path: '/knowledge',
    label: 'Знания',
    icon: BookOpen,
    hint: 'Ответы по регламентам с источниками',
    group: 'main',
  },
  {
    path: '/integrations',
    label: 'Интеграции',
    icon: Cable,
    hint: 'Битрикс24, 1С, Telegram, сверка',
    group: 'main',
  },
  {
    path: '/copilot',
    label: 'Копилот',
    icon: Bot,
    hint: 'Спросите своими словами — агент с инструментами',
    group: 'ai',
  },
  {
    path: '/under-the-hood',
    label: 'Под капотом',
    icon: Cpu,
    hint: 'Архитектура, трассировка агента, бюджет',
    group: 'ai',
  },
  { path: '/work', label: 'Путь заказчика', icon: Route, hint: 'От созвона до сопровождения', group: 'work' },
  {
    path: '/work/roadmap',
    label: 'Дорожная карта',
    icon: CalendarRange,
    hint: 'Ход разработки этого стенда',
    group: 'work',
  },
  {
    path: '/work/quality',
    label: 'Код и качество',
    icon: ShieldCheck,
    hint: 'GitHub, тесты, решения',
    group: 'work',
  },
  { path: '/design', label: 'Дизайн-система', icon: Palette, hint: 'Токены и компоненты', group: 'work' },
]

export const GITHUB_URL = 'https://github.com/ZonaNeona/pulse-ai-ops'

export function activeNav(path: string): NavItem | undefined {
  if (path === '/') return NAV[0]
  return NAV.filter((n) => n.path !== '/')
    .sort((a, b) => b.path.length - a.path.length)
    .find((n) => path === n.path || path.startsWith(n.path + '/'))
}
