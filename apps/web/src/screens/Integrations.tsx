import { Bot, Cable, Database, MessageCircle, Sparkles, type LucideIcon } from 'lucide-react'
import { useIntegrations, useReconciliation, useSyncLog } from '@/api/queries'
import { Meter } from '@/ui/charts'
import { rubShort } from '@/ui/format'
import { Badge, Button, Card, CardHeader, Dot, PageHeader, Skeleton } from '@/ui/kit'
import { useToast } from '@/ui/Toast'

const ICON: Record<string, LucideIcon> = { b24: Database, erp: Database, tg: MessageCircle, llm: Sparkles, hermes: Bot }

export function Integrations() {
  const { data: items } = useIntegrations()
  const { data: log } = useSyncLog()
  const { data: recon } = useReconciliation()
  const toast = useToast()
  return (
    <>
      <PageHeader
        eyebrow="Модуль · Интеграции"
        title="Интеграции и сверка"
        description="Все системы подключены через порты: эмулятор Битрикс24 и живой портал взаимозаменяемы одной переменной окружения."
      />
      {!items ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {items.map((it) => {
            const Icon = ICON[it.id] ?? Cable
            return (
              <Card key={it.id} className="flex flex-col">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm font-medium text-ink">
                    <Icon size={15} className="text-muted" />
                    {it.name}
                  </span>
                  <Dot tone={it.status} />
                </div>
                <div className="mt-1 text-xs text-muted">
                  {it.kind} · {it.mode}
                </div>
                <p className="mt-2 text-xs text-ink-2">{it.detail}</p>
                <dl className="mt-3 grid grid-cols-2 gap-2 border-t border-line pt-3">
                  {it.metrics.map((m) => (
                    <div key={m.label}>
                      <dt className="text-[11px] text-muted">{m.label}</dt>
                      <dd className="num text-sm font-medium text-ink">{m.value}</dd>
                    </div>
                  ))}
                </dl>
                <div className="mt-auto flex items-center justify-between pt-3 text-xs">
                  <Badge tone={it.status}>{it.statusLabel}</Badge>
                  <span className="text-faint">{it.lastSync}</span>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        {!recon ? (
          <Skeleton className="h-80" />
        ) : (
          <Card padded={false}>
            <div className="px-4 pt-4">
              <CardHeader
                title={`Сверка CRM ↔ 1С · ${recon.period}`}
                hint="Оплаченные сделки против проведённых реализаций"
                action={
                  <Button size="sm" variant="secondary" onClick={() => toast('Задачи ответственным созданы черновиками', 'success')}>
                    Задачи ответственным
                  </Button>
                }
              />
              <div className="grid gap-3 pb-4 sm:grid-cols-3">
                <Side label="CRM, оплачено" count={recon.crmDeals} amount={recon.crmAmount} />
                <Side label="1С, проведено" count={recon.erpPosted} amount={recon.erpAmount} />
                <div className="rounded-md bg-danger-soft px-3 py-2.5">
                  <div className="text-xs text-danger">Разница</div>
                  <div className="num mt-0.5 text-md font-semibold text-danger">
                    {rubShort(recon.crmAmount - recon.erpAmount)}
                  </div>
                  <div className="text-xs text-danger">{recon.gaps.length} сделки</div>
                </div>
              </div>
              <Meter value={recon.erpAmount} max={recon.crmAmount} tone="warning" className="mb-4" />
            </div>
            <table className="w-full border-t border-line text-sm">
              <tbody className="divide-y divide-line">
                {recon.gaps.map((g) => (
                  <tr key={g.deal}>
                    <td className="px-4 py-2.5">
                      <div className="text-ink">{g.client}</div>
                      <div className="text-xs text-muted">{g.issue}</div>
                    </td>
                    <td className="hidden px-3 py-2.5 text-muted md:table-cell">{g.manager}</td>
                    <td className="num px-4 py-2.5 text-right text-ink">{rubShort(g.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}

        <Card padded={false}>
          <div className="px-4 pt-4">
            <CardHeader title="Журнал обмена" hint="Синки, вебхуки, лимиты API" />
          </div>
          {!log ? (
            <Skeleton className="m-4 h-60" />
          ) : (
            <ul className="divide-y divide-line border-t border-line">
              {log.map((e, i) => (
                <li key={i} className="flex items-start gap-3 px-4 py-2.5 text-sm">
                  <span className="mono w-11 shrink-0 pt-px text-xs text-faint">{e.at}</span>
                  <Dot tone={e.status} className="mt-1.5" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-ink">{e.source}</span>
                      <span className="mono truncate text-xs text-muted">{e.event}</span>
                    </div>
                    <div className="text-xs text-muted">{e.detail}</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  )
}

function Side({ label, count, amount }: { label: string; count: number; amount: number }) {
  return (
    <div className="rounded-md bg-surface-2/70 px-3 py-2.5">
      <div className="text-xs text-muted">{label}</div>
      <div className="num mt-0.5 text-md font-semibold text-ink">{rubShort(amount)}</div>
      <div className="text-xs text-muted">{count} документов</div>
    </div>
  )
}
