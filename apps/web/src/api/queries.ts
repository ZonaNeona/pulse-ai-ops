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

export function getVisitorId(): string {
  if (typeof window === 'undefined') return 'default'
  let id = localStorage.getItem('pulse_visitor_id')
  if (!id) {
    id = 'v_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36)
    localStorage.setItem('pulse_visitor_id', id)
  }
  return id
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const visitorId = getVisitorId()
  const isForm = typeof FormData !== 'undefined' && init?.body instanceof FormData
  const headers: Record<string, string> = {
    'X-Visitor-Id': visitorId,
    ...(init?.headers as Record<string, string>),
  }
  if (!isForm && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  const res = await fetch('/api' + path, {
    ...init,
    headers,
  })
  if (!res.ok) {
    let msg = res.status === 404 ? 'Не найдено' : `Сервер ответил ${res.status}`
    try {
      const err = await res.json()
      if (err?.detail) {
        msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail)
      }
    } catch {
      // ignore
    }
    throw new Error(msg)
  }
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

// Module 06 (Docs) is live with LangGraph and SQLite checkpoints
export const useDocs = () => useData<DocItem[]>('docs', () => api('/docs'), LIVE)

export async function confirmDoc(id: number): Promise<DocItem> {
  return api<DocItem>(`/docs/${id}/confirm`, { method: 'POST' })
}

export async function rejectDoc(id: number): Promise<DocItem> {
  return api<DocItem>(`/docs/${id}/reject`, { method: 'POST' })
}

export async function uploadDoc(file: File): Promise<DocItem> {
  const data = new FormData()
  data.append('file', file)
  return api<DocItem>('/docs/upload', {
    method: 'POST',
    body: data,
  })
}

// Module 07 (Knowledge & RAG) is live
export const useKbStats = () => useData<KbStats>('kb-stats', () => api('/kb/stats'), LIVE)
export const useKbAnswer = (q?: string) =>
  useQuery({
    queryKey: ['kb-answer', q ?? 'default'],
    queryFn: () => api<KbAnswer>(q ? `/kb/answer?q=${encodeURIComponent(q)}` : '/kb/answer'),
  })

export async function askKb(question: string): Promise<KbAnswer> {
  return api<KbAnswer>('/kb/ask', {
    method: 'POST',
    body: JSON.stringify({ question }),
  })
}

// Design dataset until their modules land.
export const useLastTrace = () => useData<TraceRun>('trace', () => api('/trace/latest'), LIVE)
export const useChat = () => useData<ChatMessage[]>('chat', local(demo.CHAT))
