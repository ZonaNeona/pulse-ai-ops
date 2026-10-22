import { Inbox, Plus, Sparkles } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { PULSE } from '@/mock/demo'
import { Meter, Ring, Sparkline } from '@/ui/charts'
import {
  Avatar,
  Badge,
  Button,
  Card,
  CardHeader,
  Delta,
  Dot,
  Empty,
  Kbd,
  Notice,
  PageHeader,
  Segmented,
  Skeleton,
  Toggle,
  type Tone,
} from '@/ui/kit'
import { Stat } from '@/ui/Stat'
import { useToast } from '@/ui/Toast'

const COLORS = [
  ['bg', 'Фон'],
  ['surface', 'Поверхность'],
  ['surface-2', 'Поверхность 2'],
  ['surface-3', 'Поверхность 3'],
  ['border', 'Граница'],
  ['text', 'Текст'],
  ['muted', 'Вторичный текст'],
  ['accent', 'Акцент'],
  ['success', 'Успех'],
  ['warning', 'Внимание'],
  ['danger', 'Опасность'],
  ['info', 'Информация'],
]
const TYPE = [
  ['3xl', 40, 'Заголовок лендинга'],
  ['2xl', 32, 'Крупная цифра'],
  ['xl', 24, 'Заголовок страницы'],
  ['lg', 20, 'Заголовок раздела'],
  ['md', 16, 'Заголовок карточки'],
  ['base', 14, 'Основной текст интерфейса'],
  ['sm', 13, 'Таблицы и подписи'],
  ['xs', 12, 'Метки и подсказки'],
] as const
const TONES: Tone[] = ['neutral', 'accent', 'success', 'warning', 'danger', 'info']

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader title={title} />
      {children}
    </Card>
  )
}

export function DesignSystem() {
  const [seg, setSeg] = useState('week')
  const [on, setOn] = useState(true)
  const toast = useToast()
  return (
    <>
      <PageHeader
        eyebrow="Проект"
        title="Дизайн-система"
        description="Токены и компоненты, из которых собраны все экраны и Mini App. Шаг сетки 4 px, Inter и JetBrains Mono, одна акцентная краска, две темы."
      />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 [&>*]:min-w-0">
        <Section title="Цвета">
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
            {COLORS.map(([token, label]) => (
              <div key={token}>
                <div className="h-12 rounded-md border border-line" style={{ background: `var(--${token})` }} />
                <div className="mt-1.5 text-xs text-ink">{label}</div>
                <div className="mono text-[11px] text-muted">--{token}</div>
              </div>
            ))}
          </div>
        </Section>
        <Section title="Типографика">
          <div className="flex flex-col gap-2">
            {TYPE.map(([name, px, sample]) => (
              <div key={name} className="flex items-baseline gap-4">
                <span className="mono w-16 shrink-0 text-xs text-muted">
                  {name} · {px}
                </span>
                <span className="min-w-0 truncate font-semibold tracking-[-0.02em] text-ink" style={{ fontSize: px, lineHeight: 1.2 }}>
                  {sample}
                </span>
              </div>
            ))}
            <div className="mt-2 flex items-baseline gap-4">
              <span className="mono w-16 shrink-0 text-xs text-muted">mono</span>
              <span className="mono text-base text-ink">1 234 567,89 ₽ · 16:42 · run_8f2c</span>
            </div>
          </div>
        </Section>
        <Section title="Кнопки и элементы управления">
          <div className="flex flex-wrap items-center gap-2">
            <Button icon={<Plus size={14} />}>Основная</Button>
            <Button variant="secondary">Вторичная</Button>
            <Button variant="ghost">Тихая</Button>
            <Button variant="danger">Опасная</Button>
            <Button loading>Загрузка</Button>
            <Button size="sm" variant="secondary">
              Маленькая
            </Button>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <Segmented
              options={[
                { id: 'day', label: 'День' },
                { id: 'week', label: 'Неделя' },
                { id: 'month', label: 'Месяц' },
              ]}
              value={seg}
              onChange={setSeg}
            />
            <Toggle checked={on} onChange={setOn} label="Пример переключателя" />
            <span className="flex items-center gap-1 text-sm text-muted">
              <Kbd>⌘</Kbd>
              <Kbd>K</Kbd> палитра команд
            </span>
            <Button variant="secondary" size="sm" onClick={() => toast('Уведомление показано', 'success')}>
              Показать тост
            </Button>
          </div>
        </Section>
        <Section title="Статусы">
          <div className="flex flex-wrap gap-2">
            {TONES.map((t) => (
              <Badge key={t} tone={t} dot>
                {t}
              </Badge>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-4">
            {TONES.map((t) => (
              <Dot key={t} tone={t} pulse={t === 'danger'} />
            ))}
            <Delta value={12} />
            <Delta value={-8} />
            <Delta value={15} invert />
            <Avatar name="Марина Соколова" seed={2} />
            <Avatar name="Павел Орлов" seed={5} size={36} />
          </div>
          <div className="mt-4 flex flex-col gap-2">
            <Notice tone="info">Данные обновляются раз в 5 минут.</Notice>
            <Notice tone="warning" icon={<Sparkles size={15} />}>
              Ответ собран из кэша: дневной лимит модели исчерпан.
            </Notice>
          </div>
        </Section>
        <Section title="Данные">
          <div className="grid gap-3 sm:grid-cols-2">
            <Stat kpi={PULSE.kpis[0]} />
            <Stat kpi={PULSE.kpis[1]} />
          </div>
          <div className="mt-4 flex items-center gap-4">
            <Ring value={77} max={100} size={48} tone="success">
              77
            </Ring>
            <div className="flex-1">
              <Meter value={64} max={100} tone="warning" />
              <Sparkline values={[3, 5, 4, 7, 6, 9, 8, 11]} className="mt-3" />
            </div>
          </div>
        </Section>
        <Section title="Состояния">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-20" />
            </div>
            <Empty icon={<Inbox size={18} />} title="Пока пусто" text="Здесь появятся документы, когда придут на почту" />
          </div>
        </Section>
      </div>
    </>
  )
}
