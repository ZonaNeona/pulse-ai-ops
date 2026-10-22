// Data hooks for every screen; everything comes from the API.
import { useQuery } from '@tanstack/react-query'
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
  KbDocument,
  KbStats,
  Manager,
  Overview,
  Reconciliation,
  SalesPulse,
  SyncEvent,
  TraceRun,
} from './types'

/** All calls go to the same origin: the server keeps the visitor's session in an HttpOnly cookie. */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = typeof FormData !== 'undefined' && init?.body instanceof FormData
  const headers: Record<string, string> = { ...(init?.headers as Record<string, string>) }
  if (!isForm && init?.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json'
  const res = await fetch('/api' + path, { ...init, headers, credentials: 'same-origin' })
  if (!res.ok) {
    let msg = res.status === 404 ? 'Не найдено' : `Сервер ответил ${res.status}`
    try {
      const err = await res.json()
      if (typeof err?.detail === 'string') msg = err.detail
      else if (res.status === 422) msg = 'Проверьте ввод'
    } catch {
      // the body is not JSON: keep the status message
    }
    throw new Error(msg)
  }
  return (await res.json()) as T
}

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
  useData<Call[]>(
    `calls:${manager ?? ''}`,
    () => api(`/sales/calls${manager ? `?manager=${manager}` : ''}`),
    LIVE,
  )
export const useCallReview = (id: number | null) =>
  useQuery({
    queryKey: ['call', id],
    queryFn: () => api<CallReview>(`/sales/calls/${id}`),
    enabled: id !== null,
  })
export const useIntegrations = () => useData<Integration[]>('integrations', () => api('/integrations'), LIVE)
export const useSyncLog = () => useData<SyncEvent[]>('sync-log', () => api('/integrations/log'), LIVE)
export const useReconciliation = () =>
  useData<Reconciliation>('recon', () => api('/integrations/reconciliation'))
export const useBudget = () => useData<Budget>('budget', () => api('/budget'), LIVE)

export const useDocs = () => useData<DocItem[]>('docs', () => api('/docs'), LIVE)
export const useDocsGraph = () => useData<{ mermaid: string }>('docs-graph', () => api('/docs/graph'))
export const decideDoc = (id: number, approve: boolean) =>
  api<DocItem>(`/docs/${id}/${approve ? 'approve' : 'reject'}`, { method: 'POST' })

export async function uploadDoc(file: File): Promise<DocItem> {
  const data = new FormData()
  data.append('file', file)
  return api<DocItem>('/docs/upload', { method: 'POST', body: data })
}

export const useKbStats = () => useData<KbStats>('kb-stats', () => api('/kb/stats'))
export const useKbDocuments = () => useData<KbDocument[]>('kb-docs', () => api('/kb/documents'))
export const askKb = (question: string) =>
  api<KbAnswer>('/kb/ask', { method: 'POST', body: JSON.stringify({ question }) })

export interface AgentsInfo {
  tools: { name: string; description: string; writes: boolean }[]
  model: string
  visionModel: string
  hermes: boolean
}
export const useAgents = () => useData<AgentsInfo>('agents', () => api('/agents'))
export const useLastTrace = () => useData<TraceRun | null>('trace', () => api('/trace/latest'), LIVE)
export const askCopilot = (message: string) =>
  api<ChatMessage>('/copilot/chat', { method: 'POST', body: JSON.stringify({ message }) })
export const decideDraft = (id: string, confirm: boolean) =>
  api<{ draft_id: string; status: string }>(`/drafts/${id}/${confirm ? 'confirm' : 'discard'}`, {
    method: 'POST',
  })
export const useBotStatus = () =>
  useData<{ connected: boolean; miniAppUrl: string; commands: { command: string; description: string }[] }>(
    'bot',
    () => api('/bot/status'),
  )
