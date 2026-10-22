// The development of this stand, written the way a client project is tracked: releases → stages → tasks,
// each task with the result it gives, an estimate, a date and a way to check it. Statuses move
// planned → done → verified (works on the public stand) → accepted (the owner signed it off).

export type TaskStatus = 'planned' | 'done' | 'verified' | 'accepted' | 'waiting'

export interface Task {
  code: string
  title: string
  /** What the client gets, in plain words. */
  outcome: string
  from: string
  to?: string
  /** Estimate in minutes. */
  min: number
  status: TaskStatus
  /** How to check it yourself: a screen of the stand or a file on GitHub. */
  check?: { label: string; href: string }
  control?: boolean
}

export interface Stage {
  title: string
  goal: string
  tasks: Task[]
}

export interface Release {
  code: string
  title: string
  milestone: string
  stages: Stage[]
}

export interface JournalEntry {
  date: string
  title: string
  text: string
}

const GH = 'https://github.com/ZonaNeona/pulse-ai-ops/blob/main/'

export const PROJECT = {
  name: 'Демо-стенд «Пульс»',
  client: 'Внутренний проект · показ заказчикам',
  updated: '2026-10-22',
  range: ['2026-10-22', '2026-10-31'] as [string, string],
}

export const RELEASES: Release[] = [
  {
    code: 'Р-1',
    title: 'Каркас, дизайн и данные',
    milestone: 'Платформа открывается и показывает живую компанию',
    stages: [
      {
        title: 'План и каркас',
        goal: 'Понятно, что строим и как проверить; репозиторий с проверками качества.',
        tasks: [
          {
            code: 'КАР-01',
            title: 'План стенда: модули, два контура, бюджет ИИ',
            outcome: 'Владелец видит, что и в каком порядке будет сделано.',
            from: '2026-10-22',
            min: 120,
            status: 'accepted',
          },
          {
            code: 'КАР-02',
            title: 'Репозиторий: линтеры, типы, тесты, CI, проверка секретов',
            outcome: 'Каждое изменение проходит автоматические проверки.',
            from: '2026-10-22',
            min: 90,
            status: 'accepted',
            check: { label: 'CI на GitHub', href: 'https://github.com/ZonaNeona/pulse-ai-ops/actions' },
          },
          {
            code: 'КАР-03',
            title: 'Снять образцы ответов REST с демо-портала Битрикс24',
            outcome: 'Эмулятор отвечает в настоящем формате Битрикс24.',
            from: '2026-10-22',
            min: 60,
            status: 'accepted',
          },
        ],
      },
      {
        title: 'Дизайн-система и оболочка',
        goal: 'Единый вид всех экранов в светлой и тёмной теме, на телефоне и в Telegram.',
        tasks: [
          {
            code: 'ДС-01',
            title: 'Токены, темы, компоненты, страница дизайн-системы',
            outcome: 'Экраны собираются из готовых проверенных деталей.',
            from: '2026-10-22',
            min: 240,
            status: 'accepted',
            check: { label: 'Дизайн-система', href: '#/design' },
          },
          {
            code: 'ДС-02',
            title: 'Оболочка: меню модулей, поиск ⌘K, переключение темы',
            outcome: 'Любой экран — в один клик или с клавиатуры.',
            from: '2026-10-22',
            min: 120,
            status: 'accepted',
            check: { label: 'Открыть ⌘K', href: '#/' },
          },
          {
            code: 'Р-1.2.К',
            title: 'Ревью дизайна владельцем: скриншоты в двух темах',
            outcome: 'Внешний вид согласован до работы с данными.',
            from: '2026-10-22',
            min: 30,
            status: 'accepted',
            control: true,
          },
        ],
      },
      {
        title: 'Данные и эмуляторы',
        goal: 'Правдоподобная компания, которая каждый день живёт заново.',
        tasks: [
          {
            code: 'ДАН-01',
            title: 'Генератор компании «Норд Инжиниринг» с сюжетом дня',
            outcome: 'В данных есть проблемы, которые система должна найти.',
            from: '2026-10-22',
            min: 180,
            status: 'accepted',
          },
          {
            code: 'ДАН-02',
            title: 'Эмулятор Битрикс24 и адаптер живого портала',
            outcome: 'Подключение настоящего портала — одна настройка.',
            from: '2026-10-22',
            min: 180,
            status: 'accepted',
            check: { label: 'crm/ на GitHub', href: GH + 'apps/api/pulse/crm' },
          },
          {
            code: 'ДАН-03',
            title: 'Эмулятор 1С в формате OData и синхронизация',
            outcome: 'Остатки, оплаты и реализации приходят как из 1С.',
            from: '2026-10-22',
            min: 150,
            status: 'accepted',
            check: { label: 'Интеграции', href: '#/integrations' },
          },
        ],
      },
    ],
  },
  {
    code: 'Р-2',
    title: 'Продажи и интеграции',
    milestone: 'РОП видит, где отдел теряет клиентов',
    stages: [
      {
        title: 'Модуль «Продажи»',
        goal: 'Пульс отдела к текущему часу и список «сделать сейчас».',
        tasks: [
          {
            code: 'ПРД-01',
            title: 'Пульс отдела и сигналы «сделать сейчас»',
            outcome: 'Пропущенные, зависшие сделки, просрочки — в одной ленте.',
            from: '2026-10-22',
            min: 180,
            status: 'verified',
            check: { label: 'Обзор', href: '#/' },
          },
          {
            code: 'ПРД-02',
            title: 'Команда: нормы к часу, оценка звонков, тренды',
            outcome: 'Видно, кто проседает, и почему.',
            from: '2026-10-22',
            min: 150,
            status: 'verified',
            check: { label: 'Команда', href: '#/sales/team' },
          },
          {
            code: 'ПРД-03',
            title: 'Сделки, воронки и звонки с разбором по 8 критериям',
            outcome: 'Разбор звонка с цитатами и советом.',
            from: '2026-10-22',
            min: 210,
            status: 'verified',
            check: { label: 'Звонки', href: '#/sales/calls' },
          },
        ],
      },
      {
        title: 'Интеграции и публикация',
        goal: 'Сверка CRM с 1С и открытая ссылка для заказчиков.',
        tasks: [
          {
            code: 'ИНТ-01',
            title: 'Статусы систем, журнал синков, сверка CRM ↔ 1С',
            outcome: 'Видно, какие оплаты не дошли до реализации в 1С.',
            from: '2026-10-22',
            min: 150,
            status: 'verified',
            check: { label: 'Сверка', href: '#/integrations' },
          },
          {
            code: 'ПУБ-01',
            title: 'Публикация: сервер, HTTPS, ночной сброс данных',
            outcome: 'Стенд открыт по ссылке, данные каждый день свежие.',
            from: '2026-10-22',
            min: 120,
            status: 'verified',
            check: { label: 'demo.shvarev-demo.ru', href: 'https://demo.shvarev-demo.ru' },
          },
        ],
      },
    ],
  },
  {
    code: 'Р-3',
    title: 'ИИ-модули',
    milestone: 'Документы, регламенты и вопросы своими словами',
    stages: [
      {
        title: 'Документы на LangGraph',
        goal: 'Входящий документ сверяется с 1С и регламентами; спорный ждёт человека.',
        tasks: [
          {
            code: 'ДОК-01',
            title: 'Граф: реквизиты → сверка → решение человека → проводка',
            outcome: 'Граф останавливается на спорном документе и продолжает после решения.',
            from: '2026-10-22',
            min: 180,
            status: 'done',
            check: { label: 'Документы', href: '#/docs' },
          },
          {
            code: 'ДОК-02',
            title: 'Проверки по 1С, CRM и регламентам со ссылкой на пункт',
            outcome: 'Видно не только что не так, но и какой пункт регламента нарушен.',
            from: '2026-10-22',
            min: 120,
            status: 'done',
            check: { label: 'checks.py', href: GH + 'apps/api/pulse/modules/docs/checks.py' },
          },
          {
            code: 'ДОК-03',
            title: 'Загрузка своего файла: PDF и TXT — правилами, фото — моделью',
            outcome: 'Заказчик проверяет систему на своём документе.',
            from: '2026-10-22',
            min: 90,
            status: 'done',
            check: { label: 'Загрузить файл', href: '#/docs' },
          },
        ],
      },
      {
        title: 'Знания',
        goal: 'Ответы по регламентам со ссылками; нет в регламентах — так и сказано.',
        tasks: [
          {
            code: 'ЗН-01',
            title: '10 регламентов компании и поиск по основам слов',
            outcome: 'Находится нужный пункт, даже если вопрос сформулирован иначе.',
            from: '2026-10-22',
            min: 150,
            status: 'done',
            check: { label: 'Знания', href: '#/knowledge' },
          },
          {
            code: 'ЗН-02',
            title: 'Ответ с проверенными ссылками и честный отказ',
            outcome: 'Модель не может сослаться на то, чего ей не давали.',
            from: '2026-10-22',
            min: 90,
            status: 'done',
          },
          {
            code: 'ЗН-03',
            title: 'Эталонная проверка: 20 вопросов и 5 вне базы',
            outcome: 'Качество поиска измерено, а не обещано.',
            from: '2026-10-22',
            min: 60,
            status: 'done',
            check: { label: 'eval.py', href: GH + 'apps/api/pulse/modules/knowledge/eval.py' },
          },
        ],
      },
      {
        title: 'Агенты',
        goal: 'Вопрос своими словами — ответ по данным, с видимым ходом и ценой.',
        tasks: [
          {
            code: 'АГ-01',
            title: 'Единый реестр инструментов: встроенный цикл, Hermes через MCP, бот',
            outcome: 'Один набор инструментов для всех каналов — нечему расходиться.',
            from: '2026-10-22',
            min: 150,
            status: 'done',
            check: { label: 'tools.py', href: GH + 'apps/api/pulse/agents/tools.py' },
          },
          {
            code: 'АГ-02',
            title: 'Мгновенные ответы на частые вопросы из инструментов',
            outcome: 'Частые вопросы бесплатны и отвечают сразу.',
            from: '2026-10-22',
            min: 90,
            status: 'done',
            check: { label: 'Копилот', href: '#/copilot' },
          },
          {
            code: 'АГ-03',
            title: 'Трассировка хода: шаги, время, стоимость от провайдера',
            outcome: 'Видно, что делал агент и сколько это стоило.',
            from: '2026-10-22',
            min: 90,
            status: 'done',
            check: { label: 'Под капотом', href: '#/under-the-hood' },
          },
          {
            code: 'АГ-04',
            title: 'Бюджет ИИ $1,5 в сутки и лимиты на посетителя',
            outcome: 'Расходы на модели не выходят за потолок.',
            from: '2026-10-22',
            min: 60,
            status: 'done',
          },
          {
            code: 'Р-3.К',
            title: 'Ревью: всё, что видит посетитель, считается из данных',
            outcome: 'На стенде нет заранее написанных результатов.',
            from: '2026-10-22',
            min: 120,
            status: 'done',
            control: true,
          },
        ],
      },
    ],
  },
  {
    code: 'Р-4',
    title: 'Каналы и запуск',
    milestone: 'Стенд в Telegram и полностью на сервере',
    stages: [
      {
        title: 'Telegram',
        goal: 'Те же данные и действия в боте и Mini App.',
        tasks: [
          {
            code: 'TG-01',
            title: 'Бот: сводка дня, команда, документы, вопросы текстом',
            outcome: 'Руководитель работает с системой из Telegram.',
            from: '2026-10-22',
            min: 150,
            status: 'done',
            check: { label: 'bot/ на GitHub', href: GH + 'apps/api/pulse/bot' },
          },
          {
            code: 'TG-02',
            title: 'Создать бота в BotFather и подключить вебхук',
            outcome: 'Бот доступен по ссылке.',
            from: '2026-10-23',
            min: 20,
            status: 'waiting',
          },
        ],
      },
      {
        title: 'Запуск',
        goal: 'Модель и Hermes на сервере, контур «Как мы работаем», упаковка репозитория.',
        tasks: [
          {
            code: 'ЗАП-01',
            title: 'Ключ модели с дневным лимитом и профиль Hermes на сервере',
            outcome: 'Свободные вопросы и загрузка фото работают на стенде.',
            from: '2026-10-22',
            to: '2026-10-23',
            min: 120,
            status: 'planned',
          },
          {
            code: 'ЗАП-02',
            title: 'Контур «Как мы работаем»: путь заказчика, дорожная карта, качество',
            outcome: 'Заказчик видит, как будет вестись его проект.',
            from: '2026-10-22',
            min: 240,
            status: 'done',
            check: { label: 'Путь заказчика', href: '#/work' },
          },
          {
            code: 'ЗАП-03',
            title: 'README и решения (ADR) по фактическому коду',
            outcome: 'Код можно оценить за 5 минут.',
            from: '2026-10-22',
            min: 120,
            status: 'done',
            check: { label: 'README на GitHub', href: 'https://github.com/ZonaNeona/pulse-ai-ops#readme' },
          },
          {
            code: 'ЗАП-04',
            title: 'Финальный проход дизайна: телефон, тёмная тема, скорость',
            outcome: 'Стенд одинаково хорош на любом экране.',
            from: '2026-10-24',
            to: '2026-10-27',
            min: 240,
            status: 'planned',
          },
          {
            code: 'Р-4.К',
            title: 'Приёмка владельцем: сценарий показа за 2 минуты',
            outcome: 'Стенд готов к ссылкам в откликах.',
            from: '2026-10-28',
            min: 60,
            status: 'planned',
            control: true,
          },
        ],
      },
    ],
  },
]

export const JOURNAL: JournalEntry[] = [
  {
    date: '2026-10-22',
    title: 'План согласован',
    text: 'Один универсальный стенд вместо стенда под каждого заказчика. Модули, два контура, бюджет ИИ $1,5 в сутки.',
  },
  {
    date: '2026-10-22',
    title: 'Сервер освобождён',
    text: 'Старые демо удалены, остался один стенд. Памяти хватает на API, модель и Hermes.',
  },
  {
    date: '2026-10-22',
    title: 'Р-1 принят, Р-2 на стенде',
    text: 'Дизайн-система и данные приняты; продажи и интеграции работают на демо-компании по открытой ссылке.',
  },
  {
    date: '2026-10-22',
    title: 'Ревью ИИ-модулей',
    text: 'Документы, знания и агенты переведены на живые данные: каждый результат на экране считается при открытии, а стоимость берётся у провайдера модели.',
  },
]

export const STATUS_LABEL: Record<TaskStatus, string> = {
  planned: 'Впереди',
  done: 'Выполнено',
  verified: 'Проверено на стенде',
  accepted: 'Принято',
  waiting: 'Ждёт владельца',
}

export const allTasks = () => RELEASES.flatMap((r) => r.stages.flatMap((s) => s.tasks))
