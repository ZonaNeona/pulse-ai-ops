import clsx from 'clsx'
import { Check, ExternalLink, X } from 'lucide-react'
import { api } from '@/api/queries'
import { useQuery } from '@tanstack/react-query'
import { GITHUB_URL } from '@/app/nav'
import { num } from '@/ui/format'
import { GithubIcon } from '@/ui/icons'
import { Badge, Button, Card, CardHeader, Empty, PageHeader, Skeleton } from '@/ui/kit'

interface Quality {
  commit: string
  measuredAt: string
  api: {
    tests: number
    passed: number
    coverage: number
    ruff: boolean
    format: boolean
    mypy: boolean
    files: number
    lines: number
  }
  web: { tests: number; passed: number; lint: boolean; typecheck: boolean; files: number; lines: number }
}

const ADR = [
  ['0001', 'CRM и 1С — только через порты', '0001-ports-and-adapters.md'],
  [
    '0002',
    'Один реестр инструментов, несколько исполнителей; LangGraph — для документов',
    '0002-agent-runtime.md',
  ],
  ['0003', 'Суточный потолок расходов на модели', '0003-ai-budget-ceiling.md'],
  ['0004', 'Правдоподобная компания вместо моков', '0004-realistic-emulator.md'],
  ['0005', 'Документы — граф LangGraph с остановкой на решении человека', '0005-langgraph-documents.md'],
  ['0006', 'Ночной сброс и «сегодня» всегда сегодня', '0006-nightly-reset.md'],
]

const CI = [
  'ruff — стиль и типичные ошибки Python',
  'mypy strict — типы во всём бэкенде',
  'pytest с покрытием — бизнес-логика, граф документов, агенты, бюджет, бот',
  'eslint и tsc — фронтенд',
  'vitest и сборка — фронтенд собирается без ошибок',
  'gitleaks — в истории нет ключей и паролей',
  'проверка, что в коде нет имён прежних заказчиков',
]

function Gate({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-ink-2">
      <span
        className={clsx(
          'grid size-4 place-items-center rounded-full',
          ok ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger',
        )}
      >
        {ok ? <Check size={10} strokeWidth={3} /> : <X size={10} strokeWidth={3} />}
      </span>
      {label}
    </span>
  )
}

function Metric({ value, label, hint }: { value: string; label: string; hint?: string }) {
  return (
    <div className="rounded-md bg-surface-2/70 px-3 py-2.5">
      <div className="num text-xl font-semibold text-ink">{value}</div>
      <div className="text-xs text-muted">{label}</div>
      {hint && <div className="text-[11px] text-faint">{hint}</div>}
    </div>
  )
}

export function QualityScreen() {
  const { data, isLoading } = useQuery({
    queryKey: ['quality'],
    queryFn: () => api<Quality | null>('/work/quality'),
  })
  return (
    <>
      <PageHeader
        eyebrow="Как мы работаем"
        title="Код и качество"
        description="Код стенда открыт. Каждое изменение проходит автоматические проверки, а цифры ниже сняты скриптом при сборке текущей версии — их нельзя «подкрутить» руками."
        actions={
          <Button
            icon={<GithubIcon size={14} />}
            onClick={() => window.open(GITHUB_URL, '_blank', 'noopener')}
          >
            Открыть репозиторий
          </Button>
        }
      />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card>
          {isLoading ? (
            <Skeleton className="h-56" />
          ) : !data ? (
            <Empty
              title="Замер ещё не сделан"
              text="Цифры появляются при сборке релиза: tools/quality_report.py"
            />
          ) : (
            <>
              <CardHeader
                title="Замер текущей версии"
                hint={`коммит ${data.commit} · ${new Date(data.measuredAt).toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })}`}
                action={
                  <a
                    href={`${GITHUB_URL}/commit/${data.commit}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                  >
                    коммит <ExternalLink size={11} />
                  </a>
                }
              />
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Metric value={`${data.api.passed}/${data.api.tests}`} label="тестов бэкенда прошли" />
                <Metric
                  value={`${String(data.api.coverage).replace('.', ',')}%`}
                  label="покрытие бэкенда"
                  hint="строк кода под тестами"
                />
                <Metric value={num(data.api.lines)} label="строк Python" hint={`${data.api.files} файлов`} />
                <Metric
                  value={num(data.web.lines)}
                  label="строк TypeScript"
                  hint={`${data.web.files} файлов`}
                />
              </div>
              <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 border-t border-line pt-4">
                <Gate ok={data.api.ruff && data.api.format} label="ruff" />
                <Gate ok={data.api.mypy} label="mypy strict" />
                <Gate ok={data.api.passed === data.api.tests} label="pytest" />
                <Gate ok={data.web.lint} label="eslint" />
                <Gate ok={data.web.typecheck} label="tsc" />
                <Gate ok={data.web.passed === data.web.tests} label="vitest" />
              </div>
            </>
          )}
        </Card>
        <Card>
          <CardHeader title="Что проверяет CI на каждый коммит" hint="GitHub Actions" />
          <ul className="flex flex-col gap-1.5 text-sm text-ink-2">
            {CI.map((c) => (
              <li key={c} className="flex gap-2">
                <Check size={14} className="mt-0.5 shrink-0 text-success" />
                {c}
              </li>
            ))}
          </ul>
          <a
            href={`${GITHUB_URL}/actions`}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-flex items-center gap-1 text-xs text-accent hover:underline"
          >
            История проверок <ExternalLink size={11} />
          </a>
        </Card>
      </div>

      <Card className="mt-4" padded={false}>
        <div className="px-4 pt-4">
          <CardHeader
            title="Архитектурные решения"
            hint="Почему сделано так, а не иначе — с альтернативами и последствиями"
          />
        </div>
        <ul className="divide-y divide-line border-t border-line">
          {ADR.map(([n, title, file]) => (
            <li key={n}>
              <a
                href={`${GITHUB_URL}/blob/main/docs/adr/${file}`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-surface-2/50"
              >
                <Badge>ADR {n}</Badge>
                <span className="flex-1 text-ink">{title}</span>
                <ExternalLink size={13} className="text-faint" />
              </a>
            </li>
          ))}
        </ul>
      </Card>
    </>
  )
}
