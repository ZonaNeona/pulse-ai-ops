// Data hooks for every screen. Live modules read the API; modules still being built (documents,
// knowledge, copilot, agent traces) resolve to the design dataset and their screens say so.
import { useQuery } from '@tanstack/react-query'
import * as demo from '@/mock/demo'
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
  SyncEvent,
  TraceRun,
} from './types'

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch('/api' + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) throw new Error(res.status === 404 ? 'Не найдено' : `Сервер ответил ${res.status}`)
  return (await res.json()) as T
}

const local =
  <T>(value: T) =>
  () =>
    Promise.resolve(value)

const useData = <T>(key: string, fetcher: () => Promise<T>, refetchInterval?: number) =>
  useQuery({ queryKey: [key], queryFn: fetcher, refetchInterval })

// The demo day unfolds live (new calls every few minutes), so the operational screens refresh themselves.
const LIVE = 60_000

export const useOverview = () => useData<Overview>('overview', () => api('/overview'), LIVE)
export const usePulse = () => useData<SalesPulse>('pulse', () => api('/sales/pulse'), LIVE)
export const useTeam = () => useData<Manager[]>('team', () => api('/sales/team'), LIVE)
export const useFunnels = () => useData<Funnel[]>('funnels', () => api('/sales/funnels'))
export const useDeals = () => useData<Deal[]>('deals', () => api('/sales/deals'), LIVE)
export const useCalls = (manager?: string | null) =>
  useData<Call[]>(`calls:${manager ?? ''}`, () => api(`/sales/calls${manager ? `?manager=${manager}` : ''}`), LIVE)
export const useCallReview = (id: number | null) =>
  useQuery({ queryKey: ['call', id], queryFn: () => api<CallReview>(`/sales/calls/${id}`), enabled: id !== null })
export const useIntegrations = () => useData<Integration[]>('integrations', () => api('/integrations'), LIVE)
export const useSyncLog = () => useData<SyncEvent[]>('sync-log', () => api('/integrations/log'), LIVE)
export const useReconciliation = () => useData<Reconciliation>('recon', () => api('/integrations/reconciliation'))
export const useBudget = () => useData<Budget>('budget', () => api('/budget'), LIVE)

// Design dataset until their modules land.
export const useDocs = () => useData<DocItem[]>('docs', local(demo.DOCS))
export const useKbStats = () => useData<KbStats>('kb-stats', local(demo.KB_STATS))
export const useKbAnswer = () => useData<KbAnswer>('kb-answer', local(demo.KB_ANSWER))
export const useLastTrace = () => useData<TraceRun>('trace', local(demo.TRACE))
export const useChat = () => useData<ChatMessage[]>('chat', local(demo.CHAT))
