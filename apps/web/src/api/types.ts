// API contract shared by the web app and the Mini App. The backend returns exactly these shapes.
import type { Tone } from '@/ui/kit'

export type ModuleId = 'sales' | 'docs' | 'knowledge' | 'integrations' | 'agents'
export type Severity = 'high' | 'medium' | 'low'
export type Unit = 'count' | 'rub' | 'pct' | 'min' | 'sec' | 'score'

export interface Company {
  name: string
  industry: string
  today: string
  timezone: string
}

export interface Kpi {
  key: string
  label: string
  value: number | null
  unit: Unit
  delta: number | null
  invert?: boolean
  spark: number[]
  hint: string
  tone: Tone
  target?: number
}

export interface ModuleHealth {
  id: ModuleId
  title: string
  status: Tone
  headline: string
  detail: string
  href: string
}

export interface ActionItem {
  id: string
  module: ModuleId
  severity: Severity
  title: string
  reason: string
  action: string
  owner?: string
  age: string
  href: string
}

export interface Overview {
  company: Company
  modules: ModuleHealth[]
  kpis: Kpi[]
  actions: ActionItem[]
  revenue: { fact: number; plan: number; forecast: number; daysLeft: number }
}

export interface Manager {
  id: number
  name: string
  role: 'hunter' | 'farmer' | 'newbie'
  roleLabel: string
  callsToday: number
  callsNorm: number
  talkMin: number
  talkNorm: number
  quality: number
  overdue: number
  deals: number
  pipeline: number
  trend: number[]
  status: Tone
  note: string
}

export interface Signal {
  id: string
  rule: string
  ruleLabel: string
  severity: Severity
  title: string
  reason: string
  manager: string
  client: string
  ageHours: number
  action: string
  href?: string
}

export interface SeriesPoint {
  key: string
  label: string
  weekend: boolean
  out: number
  in: number
  missed: number
}

export interface SalesPulse {
  kpis: Kpi[]
  series: SeriesPoint[]
  signals: Signal[]
}

export interface Funnel {
  id: string
  name: string
  stages: { id: string; name: string; tone: Tone }[]
}

export interface Deal {
  id: number
  title: string
  client: string
  amount: number
  funnel: string
  stage: string
  manager: string
  daysIdle: number
  nextStep: string | null
}

export interface Call {
  id: number
  manager: string
  managerId: number
  client: string
  direction: 'in' | 'out'
  durationSec: number
  at: string
  score: number | null
  outcome: string
  missed: boolean
}

export interface CallCriterion {
  key: string
  label: string
  weight: number
  score: number
  max: number
  quote?: string
  comment: string
}

export interface CallReview {
  call: Call
  summary: string
  advice: string[]
  criteria: CallCriterion[]
  transcript: { speaker: 'manager' | 'client'; t: number; text: string; mark?: boolean }[]
  waveform: number[]
}

export type DocStatus = 'recognized' | 'mismatch' | 'review' | 'posted'
export type StepStatus = 'done' | 'active' | 'waiting' | 'error' | 'skipped'

export interface GraphStep {
  node: string
  label: string
  status: StepStatus
  ms?: number
  note?: string
}

export interface DocField {
  key: string
  label: string
  value: string
  confidence: number
  expected?: string
}

export interface DocItem {
  id: number
  kind: 'invoice' | 'contract' | 'upd' | 'act'
  kindLabel: string
  number: string
  date: string
  counterparty: string
  amount: number
  status: DocStatus
  confidence: number
  receivedAgo: string
  steps: GraphStep[]
  fields: DocField[]
  checks: { label: string; ok: boolean; detail: string }[]
}

export interface KbSource {
  id: number
  title: string
  section: string
  quote: string
}

export interface KbAnswer {
  question: string
  answer: string
  sources: KbSource[]
  grounded: boolean
}

export interface KbStats {
  documents: number
  chunks: number
  grounded: number
  evalPassed: number
  evalTotal: number
  refusalsCorrect: number
  refusalsTotal: number
}

export interface Integration {
  id: string
  name: string
  kind: string
  mode: string
  status: Tone
  statusLabel: string
  lastSync: string
  detail: string
  metrics: { label: string; value: string }[]
}

export interface SyncEvent {
  at: string
  source: string
  event: string
  detail: string
  status: Tone
}

export interface Reconciliation {
  period: string
  crmDeals: number
  crmAmount: number
  erpPosted: number
  erpAmount: number
  gaps: { deal: string; dealId?: number; client: string; amount: number; issue: string; manager: string }[]
}

export interface TraceStep {
  id: string
  kind: 'llm' | 'tool' | 'subagent' | 'graph'
  name: string
  label: string
  lane: string
  startMs: number
  durMs: number
  detail?: string
  costUsd?: number
}

export interface TraceRun {
  id: string
  question: string
  engine: 'hermes' | 'fallback'
  model: string
  startedAgo: string
  totalMs: number
  costUsd: number
  tokens: number
  steps: TraceStep[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  sources?: { label: string; href: string }[]
  trace?: TraceRun
  cached?: boolean
}

export interface Budget {
  spentUsd: number
  capUsd: number
  questionsLeft: number
  questionsCap: number
  documentsLeft: number
  documentsCap: number
  byHour: number[]
}
