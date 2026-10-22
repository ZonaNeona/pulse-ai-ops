// Design-stage data for the fictional company. The backend seed (seed/) replaces it in stage 3;
// shapes match api/types.ts exactly, so screens do not change when the API arrives.
import type {
  Budget,
  Call,
  CallReview,
  ChatMessage,
  Deal,
  DocItem,
  Funnel,
  Integration,
  KbAnswer,
  KbStats,
  Manager,
  Overview,
  Reconciliation,
  SalesPulse,
  SeriesPoint,
  Signal,
  SyncEvent,
  TraceRun,
} from '@/api/types'

function rng(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
const r = rng(7)
const int = (a: number, b: number) => Math.floor(a + r() * (b - a + 1))
const pick = <T>(xs: T[]) => xs[int(0, xs.length - 1)]

export const COMPANY = {
  name: 'Норд Инжиниринг',
  industry: 'Поставка и монтаж инженерного оборудования',
  today: '22 октября, среда',
  timezone: 'Europe/Moscow',
}

export const MANAGERS: Manager[] = [
  ['Алексей Воронов', 'hunter', 58, 61, 142, 86, 3, 18, 'success', 'Стабильно выше нормы'],
  ['Марина Соколова', 'farmer', 44, 47, 118, 91, 1, 24, 'success', 'Лучшая оценка звонков'],
  ['Дмитрий Лебедев', 'hunter', 21, 60, 46, 58, 7, 15, 'danger', 'Просел: звонков в 3 раза меньше нормы'],
  ['Ольга Кузнецова', 'farmer', 39, 45, 104, 79, 2, 21, 'warning', '2 клиента без касания > 14 дней'],
  ['Павел Орлов', 'newbie', 33, 40, 71, 64, 4, 9, 'warning', 'Новичок, 3-я неделя'],
  ['Елена Морозова', 'farmer', 47, 45, 126, 84, 0, 19, 'success', 'Закрыла 3 сделки за неделю'],
].map(([name, role, calls, norm, talk, quality, overdue, deals, status, note], i) => ({
  id: i + 1,
  name: name as string,
  role: role as Manager['role'],
  roleLabel: role === 'hunter' ? 'Новые клиенты' : role === 'farmer' ? 'Действующие клиенты' : 'Стажёр',
  callsToday: calls as number,
  callsNorm: norm as number,
  talkMin: talk as number,
  talkNorm: 120,
  quality: quality as number,
  overdue: overdue as number,
  deals: deals as number,
  pipeline: int(18, 64) * 100_000,
  trend: Array.from({ length: 10 }, () => int(20, 70)),
  status: status as Manager['status'],
  note: note as string,
}))

export const CLIENTS = [
  'ГК «СтройМонолит»',
  'ТехПарк «Северный»',
  'Клиника «Медиус»',
  'Логистик-Центр «Восток»',
  'Завод «Термаль»',
  'БЦ «Невский 38»',
  'ЖК «Зелёный квартал»',
  'ООО «Аквалайн»',
  'ТЦ «Галерея Парк»',
  'Гостиница «Онега»',
]

const DAYS = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
export const SERIES: SeriesPoint[] = Array.from({ length: 14 }, (_, i) => {
  const date = new Date(2026, 9, 9 + i)
  const wd = (date.getDay() + 6) % 7
  const weekend = wd >= 5
  const k = weekend ? 0.15 : 1
  return {
    key: date.toISOString().slice(0, 10),
    label: `${date.getDate()} ${DAYS[wd]}`,
    weekend,
    out: Math.round(int(150, 210) * k),
    in: Math.round(int(60, 95) * k),
    missed: Math.round(int(4, 16) * k),
  }
})

export const SIGNALS: Signal[] = [
  {
    id: 's1',
    rule: 'no-callback',
    ruleLabel: 'Пропущенный без перезвона',
    severity: 'high',
    title: 'Клиника «Медиус» звонила 2 раза',
    reason: 'Последний пропущенный — 2 ч 10 мин назад, перезвона нет',
    manager: 'Дмитрий Лебедев',
    client: 'Клиника «Медиус»',
    ageHours: 2,
    action: 'Перезвонить сейчас',
  },
  {
    id: 's2',
    rule: 'stale-deal',
    ruleLabel: 'Сделка без движения',
    severity: 'high',
    title: 'КП на 2,4 млн ₽ — тишина 9 дней',
    reason: 'Стадия «КП отправлено», нет звонков и задач с 13 октября',
    manager: 'Ольга Кузнецова',
    client: 'Завод «Термаль»',
    ageHours: 216,
    action: 'Уточнить решение у ЛПР',
  },
  {
    id: 's3',
    rule: 'overdue-task',
    ruleLabel: 'Просроченная задача',
    severity: 'medium',
    title: 'Выезд замерщика не назначен',
    reason: 'Задача просрочена на 2 дня',
    manager: 'Павел Орлов',
    client: 'БЦ «Невский 38»',
    ageHours: 50,
    action: 'Назначить дату выезда',
  },
  {
    id: 's4',
    rule: 'lead-no-action',
    ruleLabel: 'Лид без действия',
    severity: 'medium',
    title: 'Заявка с сайта: вентиляция склада 3 000 м²',
    reason: 'Лид создан 5 ч назад, ответственный не связался',
    manager: 'Алексей Воронов',
    client: 'Логистик-Центр «Восток»',
    ageHours: 5,
    action: 'Связаться в течение часа',
  },
  {
    id: 's5',
    rule: 'low-score',
    ruleLabel: 'Звонок ниже порога',
    severity: 'low',
    title: 'Оценка 41 из 100: не выяснена потребность',
    reason: 'Менеджер сразу назвал цену, не задал ни одного вопроса',
    manager: 'Дмитрий Лебедев',
    client: 'ЖК «Зелёный квартал»',
    ageHours: 26,
    action: 'Разобрать звонок на планёрке',
  },
]

export const PULSE: SalesPulse = {
  kpis: [
    { key: 'calls', label: 'Звонки сегодня', value: 242, unit: 'count', delta: 6, spark: SERIES.map((s) => s.out + s.in), hint: 'исходящие и входящие', tone: 'neutral' },
    { key: 'missed', label: 'Без перезвона', value: 3, unit: 'count', delta: -40, invert: true, spark: SERIES.map((s) => s.missed), hint: 'из 11 пропущенных', tone: 'danger' },
    { key: 'callback', label: 'Медиана перезвона', value: 14, unit: 'min', delta: -12, invert: true, spark: [22, 19, 25, 17, 16, 18, 14, 15, 13, 14], hint: 'цель — до 15 минут', tone: 'success' },
    { key: 'newDeals', label: 'Новые сделки', value: 9, unit: 'count', delta: 12, spark: [5, 7, 6, 9, 8, 4, 7, 10, 8, 9], hint: 'за сегодня', tone: 'neutral' },
    { key: 'stale', label: 'Сделки без движения', value: 7, unit: 'count', delta: 17, invert: true, spark: [4, 5, 5, 6, 6, 7, 6, 7, 7, 7], hint: 'больше 7 дней', tone: 'warning' },
    { key: 'quality', label: 'Оценка звонков', value: 77, unit: 'score', delta: 3, spark: [71, 72, 74, 73, 75, 76, 74, 77, 76, 77], hint: 'средняя за неделю', tone: 'neutral' },
  ],
  series: SERIES,
  signals: SIGNALS,
}

export const FUNNELS: Funnel[] = [
  {
    id: 'supply',
    name: 'Поставка',
    stages: [
      { id: 'new', name: 'Новая', tone: 'neutral' },
      { id: 'need', name: 'Выявление потребности', tone: 'info' },
      { id: 'offer', name: 'КП отправлено', tone: 'accent' },
      { id: 'invoice', name: 'Счёт выставлен', tone: 'warning' },
      { id: 'paid', name: 'Оплачено', tone: 'success' },
    ],
  },
  {
    id: 'install',
    name: 'Монтаж',
    stages: [
      { id: 'survey', name: 'Замер', tone: 'neutral' },
      { id: 'project', name: 'Проект и смета', tone: 'info' },
      { id: 'contract', name: 'Договор', tone: 'accent' },
      { id: 'works', name: 'Монтаж', tone: 'warning' },
      { id: 'accepted', name: 'Акт подписан', tone: 'success' },
    ],
  },
  {
    id: 'service',
    name: 'Сервис',
    stages: [
      { id: 'request', name: 'Заявка', tone: 'neutral' },
      { id: 'diagnose', name: 'Диагностика', tone: 'info' },
      { id: 'repair', name: 'Ремонт', tone: 'warning' },
      { id: 'done', name: 'Выполнено', tone: 'success' },
    ],
  },
]

const ITEMS = [
  'Приточная установка',
  'Чиллер 120 кВт',
  'Насосная группа',
  'ИТП под ключ',
  'Вентиляция склада',
  'Автоматика котельной',
  'VRF-система',
  'Тепловая завеса',
  'Сервис по договору',
]
export const DEALS: Deal[] = FUNNELS.flatMap((f) =>
  f.stages.flatMap((s) =>
    Array.from({ length: int(2, 5) }, () => {
      const client = pick(CLIENTS)
      const idle = int(0, 16)
      return {
        id: int(1200, 9800),
        title: `${pick(ITEMS)} — ${client.split('«')[1]?.replace('»', '') ?? client}`,
        client,
        amount: int(3, 60) * 50_000,
        funnel: f.id,
        stage: s.id,
        manager: pick(MANAGERS).name,
        daysIdle: idle,
        nextStep: idle > 9 ? null : pick(['Звонок ЛПР', 'Отправить КП', 'Выезд на объект', 'Согласовать смету']),
      }
    }),
  ),
)

export const CALLS: Call[] = Array.from({ length: 24 }, (_, i): Call => {
  const m = MANAGERS[i % MANAGERS.length]
  const missed = i % 9 === 4
  return {
    id: 3000 + i,
    manager: m.name,
    managerId: m.id,
    client: pick(CLIENTS),
    direction: i % 3 === 0 ? 'in' : 'out',
    durationSec: missed ? 0 : int(40, 620),
    at: `${String(16 - Math.floor(i / 3)).padStart(2, '0')}:${String(int(0, 59)).padStart(2, '0')}`,
    score: missed ? null : m.name === 'Дмитрий Лебедев' ? int(35, 58) : int(62, 94),
    outcome: missed ? 'Пропущен' : pick(['Договорились о замере', 'Отправить КП', 'Перезвонить завтра', 'Уточнение по счёту', 'Не ЛПР']),
    missed,
  }
}).sort((a, b) => b.at.localeCompare(a.at))

export const CALL_REVIEW: CallReview = {
  call: { ...CALLS[1], score: 64, durationSec: 312, manager: 'Павел Орлов', client: 'БЦ «Невский 38»', outcome: 'Договорились о замере' },
  summary:
    'Клиент планирует замену вентиляции на двух этажах. Менеджер договорился о замере, но не выяснил бюджет и сроки, а цену назвал до понимания объёма.',
  advice: [
    'Спросить о бюджете и сроке запуска до разговора о цене',
    'Зафиксировать ЛПР: кто подписывает договор',
    'Назначить дату замера в разговоре, а не «созвонимся»',
  ],
  criteria: [
    { key: 'greeting', label: 'Приветствие и представление', weight: 5, score: 5, max: 5, comment: 'Представился, назвал компанию' },
    { key: 'needs', label: 'Выявление потребности', weight: 25, score: 12, max: 25, quote: 'Ну, сколько это будет стоить примерно?', comment: 'Задан 1 вопрос из 5 обязательных' },
    { key: 'lpr', label: 'Выход на ЛПР', weight: 15, score: 6, max: 15, comment: 'Не уточнил, кто принимает решение' },
    { key: 'value', label: 'Ценность решения', weight: 20, score: 15, max: 20, quote: 'Мы даём гарантию на монтаж три года', comment: 'Хорошо про гарантию и сервис' },
    { key: 'objections', label: 'Работа с возражениями', weight: 15, score: 11, max: 15, comment: 'Отработал «дорого» через рассрочку' },
    { key: 'next', label: 'Следующий шаг', weight: 20, score: 15, max: 20, quote: 'Давайте я подъеду в четверг', comment: 'Шаг есть, но без точного времени' },
  ],
  transcript: [
    { speaker: 'manager', t: 0, text: 'Добрый день! Павел, «Норд Инжиниринг». Вы оставляли заявку на вентиляцию?' },
    { speaker: 'client', t: 6, text: 'Да, у нас бизнес-центр, хотим поменять систему на третьем и четвёртом этажах.' },
    { speaker: 'manager', t: 14, text: 'Отлично. Площадь примерно какая?' },
    { speaker: 'client', t: 18, text: 'Около тысячи двухсот метров. Ну, сколько это будет стоить примерно?', mark: true },
    { speaker: 'manager', t: 26, text: 'Если по аналогам — от трёх с половиной миллионов с монтажом.' },
    { speaker: 'client', t: 34, text: 'Дороговато. Мы рассчитывали меньше.' },
    { speaker: 'manager', t: 39, text: 'Можно разбить оплату на этапы. И мы даём гарантию на монтаж три года.', mark: true },
    { speaker: 'client', t: 49, text: 'Этапы — это интересно. Что дальше?' },
    { speaker: 'manager', t: 53, text: 'Давайте я подъеду в четверг, посмотрю объект и сделаем точный расчёт.', mark: true },
    { speaker: 'client', t: 61, text: 'Хорошо, в четверг подойдёт.' },
  ],
  waveform: Array.from({ length: 120 }, (_, i) => 0.2 + Math.abs(Math.sin(i / 3.1)) * 0.5 + r() * 0.3),
}

const STEPS_OK = [
  { node: 'classify', label: 'Тип документа', status: 'done', ms: 420, note: 'УПД, уверенность 0,98' },
  { node: 'extract', label: 'Извлечение полей', status: 'done', ms: 2840, note: '14 полей' },
  { node: 'validate', label: 'Сверка с 1С и CRM', status: 'done', ms: 310, note: 'расхождений нет' },
  { node: 'review', label: 'Подтверждение', status: 'done', note: 'автоматически, уверенность > 0,95' },
  { node: 'draft', label: 'Проводка в 1С', status: 'done', ms: 180 },
] as const

export const DOCS: DocItem[] = [
  {
    id: 1,
    kind: 'invoice',
    kindLabel: 'Счёт',
    number: '№ 2417',
    date: '21.10.2026',
    counterparty: 'ООО «ВентТехСнаб»',
    amount: 421_300,
    status: 'mismatch',
    confidence: 0.93,
    receivedAgo: '12 мин назад',
    steps: [
      { node: 'classify', label: 'Тип документа', status: 'done', ms: 380, note: 'Счёт на оплату, 0,99' },
      { node: 'extract', label: 'Извлечение полей', status: 'done', ms: 3120, note: '12 полей' },
      { node: 'validate', label: 'Сверка с 1С и CRM', status: 'error', ms: 290, note: 'сумма не совпадает с заказом' },
      { node: 'review', label: 'Подтверждение', status: 'active', note: 'ждёт человека' },
      { node: 'draft', label: 'Проводка в 1С', status: 'waiting' },
    ],
    fields: [
      { key: 'supplier', label: 'Поставщик', value: 'ООО «ВентТехСнаб»', confidence: 0.99 },
      { key: 'inn', label: 'ИНН', value: '7814 562 019', confidence: 0.98 },
      { key: 'number', label: 'Номер и дата', value: '№ 2417 от 21.10.2026', confidence: 0.99 },
      { key: 'order', label: 'Основание', value: 'Заказ поставщику № ЗП-0388', confidence: 0.91 },
      { key: 'amount', label: 'Сумма с НДС', value: '421 300,00 ₽', confidence: 0.97, expected: '412 300,00 ₽' },
      { key: 'vat', label: 'НДС 20%', value: '70 216,67 ₽', confidence: 0.95 },
      { key: 'due', label: 'Оплатить до', value: '28.10.2026', confidence: 0.88 },
    ],
    checks: [
      { label: 'Контрагент есть в 1С', ok: true, detail: 'карточка поставщика, договор № 14/2025' },
      { label: 'Есть заказ-основание', ok: true, detail: 'ЗП-0388 от 14.10.2026' },
      { label: 'Сумма совпадает с заказом', ok: false, detail: 'в заказе 412 300 ₽, в счёте 421 300 ₽ (+9 000 ₽)' },
      { label: 'Счёт не оплачен ранее', ok: true, detail: 'дублей не найдено' },
    ],
  },
  {
    id: 2,
    kind: 'upd',
    kindLabel: 'УПД',
    number: '№ 1182',
    date: '21.10.2026',
    counterparty: 'АО «ТермоКомплект»',
    amount: 1_186_400,
    status: 'posted',
    confidence: 0.98,
    receivedAgo: '1 ч назад',
    steps: [...STEPS_OK],
    fields: [
      { key: 'supplier', label: 'Поставщик', value: 'АО «ТермоКомплект»', confidence: 0.99 },
      { key: 'amount', label: 'Сумма с НДС', value: '1 186 400,00 ₽', confidence: 0.99 },
    ],
    checks: [{ label: 'Сверка с заказом', ok: true, detail: 'совпадает' }],
  },
  {
    id: 3,
    kind: 'contract',
    kindLabel: 'Договор',
    number: '№ М-77/10',
    date: '20.10.2026',
    counterparty: 'Клиника «Медиус»',
    amount: 3_420_000,
    status: 'review',
    confidence: 0.86,
    receivedAgo: '3 ч назад',
    steps: [
      { node: 'classify', label: 'Тип документа', status: 'done', ms: 410, note: 'Договор подряда, 0,97' },
      { node: 'extract', label: 'Извлечение полей', status: 'done', ms: 5210, note: '18 полей, 2 неуверенно' },
      { node: 'validate', label: 'Сверка с 1С и CRM', status: 'done', ms: 340, note: 'сделка найдена' },
      { node: 'review', label: 'Подтверждение', status: 'active', note: 'уверенность ниже 0,9' },
      { node: 'draft', label: 'Проводка в 1С', status: 'waiting' },
    ],
    fields: [
      { key: 'client', label: 'Заказчик', value: 'ООО «Медиус Клиник»', confidence: 0.97 },
      { key: 'amount', label: 'Цена договора', value: '3 420 000,00 ₽', confidence: 0.96 },
      { key: 'term', label: 'Срок работ', value: '45 рабочих дней', confidence: 0.81 },
      { key: 'penalty', label: 'Неустойка', value: '0,1% в день', confidence: 0.78 },
    ],
    checks: [
      { label: 'Сделка в CRM', ok: true, detail: 'Монтаж · «Договор», 3 420 000 ₽' },
      { label: 'Неустойка в пределах политики', ok: true, detail: 'лимит 0,1% в день' },
    ],
  },
  ...['act', 'upd', 'invoice', 'upd', 'act', 'invoice'].map((kind, i) => ({
    id: 4 + i,
    kind: kind as DocItem['kind'],
    kindLabel: kind === 'act' ? 'Акт' : kind === 'upd' ? 'УПД' : 'Счёт',
    number: `№ ${int(400, 2900)}`,
    date: `${20 - i}.10.2026`,
    counterparty: pick(['ООО «ВентТехСнаб»', 'АО «ТермоКомплект»', 'ООО «Климат-Опт»', ...CLIENTS.slice(0, 4)]),
    amount: int(4, 90) * 10_000,
    status: (i === 2 ? 'recognized' : 'posted') as DocItem['status'],
    confidence: 0.9 + r() * 0.09,
    receivedAgo: `${i + 4} ч назад`,
    steps: [...STEPS_OK],
    fields: [],
    checks: [],
  })),
]

export const KB_STATS: KbStats = {
  documents: 24,
  chunks: 318,
  grounded: 94,
  evalPassed: 18,
  evalTotal: 20,
  refusalsCorrect: 5,
  refusalsTotal: 5,
}

export const KB_ANSWER: KbAnswer = {
  question: 'Какая скидка допустима для дилера без согласования с директором?',
  answer:
    'Менеджер может дать дилеру скидку до 7% от прайса самостоятельно [1]. От 7 до 12% — с согласованием РОПа в карточке сделки, больше 12% — только с директором и при предоплате не меньше 50% [2]. На оборудование под заказ скидка не действует [1].',
  sources: [
    { id: 1, title: 'Ценовая политика 2026', section: '§ 3.2 Скидки дилерам', quote: 'Скидка до 7% предоставляется менеджером самостоятельно… На позиции «под заказ» скидки не распространяются.' },
    { id: 2, title: 'Регламент согласования сделок', section: '§ 2 Уровни согласования', quote: 'Скидка свыше 12% согласуется с директором при условии предоплаты не менее 50%.' },
  ],
  grounded: true,
}

export const INTEGRATIONS: Integration[] = [
  { id: 'b24', name: 'Битрикс24', kind: 'CRM', mode: 'Эмулятор REST', status: 'success', statusLabel: 'Синхронно', lastSync: '3 мин назад', detail: 'Сделки, контакты, звонки, задачи, смарт-процессы', metrics: [{ label: 'Сделок', value: '412' }, { label: 'Звонков', value: '2 046' }, { label: 'Запросов/сутки', value: '1 380' }] },
  { id: 'erp', name: '1С:ERP', kind: 'Учёт', mode: 'Эмулятор OData', status: 'warning', statusLabel: '4 расхождения', lastSync: '5 мин назад', detail: 'Остатки, реализации, оплаты, заказы поставщикам', metrics: [{ label: 'Документов', value: '1 214' }, { label: 'Позиций', value: '386' }, { label: 'Расхождений', value: '4' }] },
  { id: 'tg', name: 'Telegram', kind: 'Канал', mode: 'Бот + Mini App', status: 'success', statusLabel: 'Онлайн', lastSync: 'сейчас', detail: 'Команды, вопросы копилоту, черновики с подтверждением', metrics: [{ label: 'Диалогов', value: '37' }, { label: 'Mini App', value: '112 открытий' }] },
  { id: 'llm', name: 'OpenRouter', kind: 'Модели', mode: 'DeepSeek · Gemini Flash', status: 'success', statusLabel: 'В бюджете', lastSync: '1 мин назад', detail: 'Агент, извлечение полей, оценка звонков', metrics: [{ label: 'Сегодня', value: '$0,42' }, { label: 'Лимит', value: '$1,50' }] },
  { id: 'hermes', name: 'Hermes Agent', kind: 'Агенты', mode: 'API-сервер, MCP', status: 'success', statusLabel: 'Готов', lastSync: '1 мин назад', detail: '23 инструмента через MCP, 4 скилла, подагенты', metrics: [{ label: 'Ходов сегодня', value: '19' }, { label: 'Среднее время', value: '6,4 с' }] },
]

export const SYNC_LOG: SyncEvent[] = [
  { at: '16:42', source: 'Битрикс24', event: 'crm.deal.list', detail: 'дельта: 6 сделок изменено', status: 'success' },
  { at: '16:41', source: '1С:ERP', event: 'Реализации', detail: '2 новых документа', status: 'success' },
  { at: '16:39', source: 'Документы', event: 'Счёт № 2417', detail: 'сумма не совпала с заказом ЗП-0388', status: 'warning' },
  { at: '16:35', source: 'Битрикс24', event: 'voximplant.statistic.get', detail: '14 звонков, 12 с записью', status: 'success' },
  { at: '16:30', source: 'Telegram', event: 'webhook', detail: '/today от посетителя', status: 'info' },
  { at: '16:12', source: 'Битрикс24', event: 'tasks.task.list', detail: 'лимит запросов: пауза 3 с', status: 'warning' },
  { at: '16:00', source: '1С:ERP', event: 'Остатки', detail: '386 позиций обновлено', status: 'success' },
]

export const RECON: Reconciliation = {
  period: 'Октябрь 2026',
  crmDeals: 38,
  crmAmount: 21_840_000,
  erpPosted: 34,
  erpAmount: 19_310_000,
  gaps: [
    { deal: 'Чиллер 120 кВт — Термаль', client: 'Завод «Термаль»', amount: 1_240_000, issue: 'Оплачено в CRM, реализации в 1С нет', manager: 'Ольга Кузнецова' },
    { deal: 'ИТП под ключ — Онега', client: 'Гостиница «Онега»', amount: 860_000, issue: 'Сумма в 1С меньше на 40 000 ₽', manager: 'Елена Морозова' },
    { deal: 'Насосная группа — Аквалайн', client: 'ООО «Аквалайн»', amount: 290_000, issue: 'Реализация на другого контрагента', manager: 'Алексей Воронов' },
    { deal: 'Тепловая завеса — Галерея', client: 'ТЦ «Галерея Парк»', amount: 140_000, issue: 'Оплачено в CRM, реализации в 1С нет', manager: 'Павел Орлов' },
  ],
}

export const TRACE: TraceRun = {
  id: 'run_8f2c',
  question: 'Сравни продажи октября с оплатами в 1С и найди, кто не провёл реализации',
  engine: 'hermes',
  model: 'deepseek-chat',
  startedAgo: '2 мин назад',
  totalMs: 7840,
  costUsd: 0.0061,
  tokens: 14_820,
  steps: [
    { id: 't1', kind: 'llm', name: 'plan', label: 'План ответа', lane: 'Hermes', startMs: 0, durMs: 1150, costUsd: 0.0009 },
    { id: 't2', kind: 'subagent', name: 'delegate_task', label: 'Подагент «Продажи»', lane: 'Подагент 1', startMs: 1200, durMs: 3100, costUsd: 0.0018 },
    { id: 't3', kind: 'tool', name: 'sales_month', label: 'sales_month(month=10)', lane: 'Подагент 1', startMs: 1500, durMs: 420, detail: '38 сделок, 21,8 млн ₽' },
    { id: 't4', kind: 'subagent', name: 'delegate_task', label: 'Подагент «1С»', lane: 'Подагент 2', startMs: 1220, durMs: 3600, costUsd: 0.0016 },
    { id: 't5', kind: 'tool', name: 'erp_sales', label: 'erp_sales(period=2026-10)', lane: 'Подагент 2', startMs: 1700, durMs: 610, detail: '34 реализации, 19,3 млн ₽' },
    { id: 't6', kind: 'tool', name: 'reconcile', label: 'reconcile(crm, erp)', lane: 'Подагент 2', startMs: 2600, durMs: 380, detail: '4 расхождения' },
    { id: 't7', kind: 'tool', name: 'find_manager', label: 'find_manager × 4', lane: 'Hermes', startMs: 4900, durMs: 520 },
    { id: 't8', kind: 'llm', name: 'answer', label: 'Ответ с источниками', lane: 'Hermes', startMs: 5500, durMs: 2340, costUsd: 0.0018 },
  ],
}

export const CHAT: ChatMessage[] = [
  { id: 'm1', role: 'user', text: TRACE.question },
  {
    id: 'm2',
    role: 'assistant',
    text: 'В октябре в CRM 38 оплаченных сделок на **21,8 млн ₽**, в 1С проведено 34 реализации на **19,3 млн ₽**. Разница — 2,53 млн ₽ в четырёх сделках:\n\n1. **Завод «Термаль»**, чиллер — 1,24 млн ₽: оплачено, реализации нет (Ольга Кузнецова).\n2. **Гостиница «Онега»**, ИТП — в 1С на 40 000 ₽ меньше (Елена Морозова).\n3. **ООО «Аквалайн»** — реализация оформлена на другого контрагента (Алексей Воронов).\n4. **ТЦ «Галерея Парк»** — 140 000 ₽, реализации нет (Павел Орлов).\n\nМогу поставить задачи ответственным с чек-листом документов.',
    sources: [
      { label: 'CRM: 38 сделок', href: '#/sales/deals' },
      { label: '1С: 34 реализации', href: '#/integrations' },
      { label: 'Сверка', href: '#/integrations' },
    ],
    trace: TRACE,
  },
]

export const PRESETS = [
  'Кто из менеджеров просел на этой неделе?',
  'Какие сделки зависли больше 7 дней?',
  'Сравни продажи октября с оплатами в 1С',
  'Разбери худший звонок за вчера',
  'Какие документы ждут подтверждения?',
  'Какая скидка допустима для дилера?',
]

export const BUDGET: Budget = {
  spentUsd: 0.42,
  capUsd: 1.5,
  questionsLeft: 8,
  questionsCap: 10,
  documentsLeft: 3,
  documentsCap: 3,
  byHour: [0, 0, 0, 0, 0, 0, 0, 0, 2, 5, 9, 6, 4, 7, 3, 4, 2, 0, 0, 0, 0, 0, 0, 0],
}

export const OVERVIEW: Overview = {
  company: COMPANY,
  revenue: { fact: 21_840_000, plan: 28_000_000, forecast: 26_900_000, daysLeft: 7 },
  modules: [
    { id: 'sales', title: 'Продажи', status: 'warning', headline: '5 сигналов', detail: '2 срочных: пропущенный без перезвона, КП без движения', href: '/sales' },
    { id: 'docs', title: 'Документы', status: 'danger', headline: '2 ждут человека', detail: 'Счёт № 2417: сумма не совпадает с заказом', href: '/docs' },
    { id: 'knowledge', title: 'Знания', status: 'success', headline: '94% с источником', detail: '18 из 20 эталонных вопросов', href: '/knowledge' },
    { id: 'integrations', title: 'Интеграции', status: 'warning', headline: '4 расхождения', detail: 'CRM ↔ 1С за октябрь: 2,53 млн ₽', href: '/integrations' },
    { id: 'agents', title: 'Агенты', status: 'success', headline: '$0,42 из $1,50', detail: '19 ходов, среднее время 6,4 с', href: '/under-the-hood' },
  ],
  kpis: [
    { key: 'revenue', label: 'Выручка октября', value: 21_840_000, unit: 'rub', delta: 8, spark: [12, 13, 15, 16, 17, 18, 19, 20, 21, 21.8], hint: 'план 28 млн ₽', tone: 'neutral', target: 28_000_000 },
    PULSE.kpis[0],
    PULSE.kpis[1],
    PULSE.kpis[4],
  ],
  actions: [
    { id: 'a1', module: 'sales', severity: 'high', title: 'Перезвонить: Клиника «Медиус»', reason: '2 пропущенных, последний 2 ч назад', action: 'Позвонить', owner: 'Дмитрий Лебедев', age: '2 ч', href: '/sales' },
    { id: 'a2', module: 'docs', severity: 'high', title: 'Счёт № 2417 — сумма больше заказа на 9 000 ₽', reason: 'ООО «ВентТехСнаб», заказ ЗП-0388', action: 'Проверить', age: '12 мин', href: '/docs?id=1' },
    { id: 'a3', module: 'integrations', severity: 'medium', title: 'Реализация не проведена: чиллер, 1,24 млн ₽', reason: 'Оплачено в CRM, в 1С документа нет', action: 'Поставить задачу', owner: 'Ольга Кузнецова', age: '3 дн', href: '/integrations' },
    { id: 'a4', module: 'sales', severity: 'medium', title: 'КП на 2,4 млн ₽ без движения 9 дней', reason: 'Завод «Термаль», стадия «КП отправлено»', action: 'Открыть сделку', owner: 'Ольга Кузнецова', age: '9 дн', href: '/sales/deals' },
    { id: 'a5', module: 'docs', severity: 'low', title: 'Договор с «Медиус» — 2 поля неуверенно', reason: 'срок работ и неустойка, уверенность < 0,85', action: 'Подтвердить', age: '3 ч', href: '/docs?id=3' },
  ],
}
