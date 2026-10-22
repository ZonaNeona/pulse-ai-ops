import {
  ArrowRight,
  CalendarRange,
  Cpu,
  MessagesSquare,
  PenTool,
  ShieldCheck,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import { navigate } from '@/app/router'
import { Card, CardHeader, PageHeader } from '@/ui/kit'

const PATH: { icon: LucideIcon; title: string; text: string; result: string }[] = [
  {
    icon: MessagesSquare,
    title: 'Созвон',
    text: 'Разбираем процесс: где теряются клиенты, деньги и время, какие системы уже есть — Битрикс24, 1С, таблицы, Telegram.',
    result: 'Список болей с цифрами',
  },
  {
    icon: PenTool,
    title: 'Схема',
    text: 'Рисуем процесс «как есть» и «как будет» и отмечаем, где работает автоматизация, а где решает человек.',
    result: 'Схема процесса в Miro',
  },
  {
    icon: CalendarRange,
    title: 'Смета',
    text: 'Дорожная карта: релизы, этапы, задачи с оценкой в часах и результатом простыми словами. Цена фиксируется до старта.',
    result: 'Дорожная карта и цена',
  },
  {
    icon: ShieldCheck,
    title: 'Исполнение',
    text: 'Вы онлайн видите статус каждой задачи, проверяете результат на своём стенде и принимаете этапы. Код — в репозитории.',
    result: 'Работающая система по этапам',
  },
  {
    icon: Wrench,
    title: 'Сопровождение',
    text: 'Абонентское обслуживание: пакет часов в месяц на доработки и поддержку, всё сверх пакета — по согласованию.',
    result: 'Система развивается вместе с бизнесом',
  },
]

const RULES = [
  [
    'Сначала только чтение',
    'Подключаемся к вашим системам на чтение. Запись — только там, где вы её разрешили.',
  ],
  ['ИИ не действует сам', 'Всё, что меняет данные, — черновик, который подтверждает человек.'],
  ['Расходы под контролем', 'У моделей ИИ — суточный потолок расходов; стоимость каждого вызова видна.'],
  ['Проверяемо', 'У каждой задачи есть способ проверить результат самому, без слов «поверьте».'],
]

export function HowWeWork() {
  return (
    <>
      <PageHeader
        eyebrow="Как мы работаем"
        title="Путь заказчика"
        description="От первого созвона до сопровождения. Этот стенд сделан по тому же процессу — его дорожная карта, код и качество открыты в соседних разделах."
      />
      <ol className="grid gap-3 md:grid-cols-5">
        {PATH.map((step, i) => (
          <li key={step.title}>
            <Card className="h-full">
              <div className="flex items-center justify-between">
                <span className="grid size-8 place-items-center rounded-md bg-accent-soft text-accent">
                  <step.icon size={16} />
                </span>
                <span className="num text-xs text-faint">0{i + 1}</span>
              </div>
              <div className="mt-3 text-md font-semibold text-ink">{step.title}</div>
              <p className="mt-1 text-sm text-ink-2">{step.text}</p>
              <div className="mt-3 border-t border-line pt-2 text-xs text-muted">
                Результат: <span className="text-ink">{step.result}</span>
              </div>
            </Card>
          </li>
        ))}
      </ol>

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        <Card>
          <CardHeader title="Правила, по которым строится система" />
          <dl className="grid gap-3 sm:grid-cols-2">
            {RULES.map(([title, text]) => (
              <div key={title} className="rounded-md bg-surface-2/70 px-3 py-2.5">
                <dt className="text-sm font-medium text-ink">{title}</dt>
                <dd className="mt-0.5 text-sm text-ink-2">{text}</dd>
              </div>
            ))}
          </dl>
        </Card>
        <Card>
          <CardHeader title="Посмотреть на примере этого стенда" />
          <div className="flex flex-col gap-1.5">
            {[
              { icon: CalendarRange, label: 'Дорожная карта разработки', href: '/work/roadmap' },
              { icon: ShieldCheck, label: 'Код и качество', href: '/work/quality' },
              { icon: Cpu, label: 'Решения и архитектура', href: '/under-the-hood' },
            ].map((l) => (
              <button
                key={l.href}
                onClick={() => navigate(l.href)}
                className="group flex cursor-pointer items-center gap-2.5 rounded-md border border-line px-3 py-2.5 text-left text-sm text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
              >
                <l.icon size={15} className="text-accent" />
                <span className="flex-1">{l.label}</span>
                <ArrowRight size={14} className="text-faint group-hover:text-accent" />
              </button>
            ))}
          </div>
        </Card>
      </div>
    </>
  )
}
