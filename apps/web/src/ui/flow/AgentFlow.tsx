// The last agent run on the canvas: question → router → the brain that answered → the tools it called →
// answer. Built from the recorded trace; the timeline under it shows the real duration of every step.
import {
  BookOpen,
  BrainCircuit,
  Cable,
  ClipboardCheck,
  FileCheck2,
  FileText,
  Gauge,
  ListChecks,
  MessageSquareText,
  PhoneCall,
  Split,
  Users,
  Warehouse,
  Wrench,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import type { TraceRun } from '@/api/types'
import { FlowCanvas, type FEdge, type FNode } from './FlowCanvas'
import { useReplay, type Frame } from './replay'
import { Timeline } from './Timeline'

const TOOL_ICON: Record<string, LucideIcon> = {
  sales_pulse: Gauge,
  get_signals: ListChecks,
  team_status: Users,
  get_deals: Cable,
  call_feed: PhoneCall,
  call_review: PhoneCall,
  reconciliation: Cable,
  erp_stock: Warehouse,
  docs_queue: FileText,
  knowledge_search: BookOpen,
  knowledge: BookOpen,
  draft_task: ClipboardCheck,
}
const COLORS = ['#34d399', '#60a5fa', '#fbbf24', '#a78bfa', '#22d3ee', '#f472b6']

const BRAIN: Record<string, { id: string; title: string; icon: LucideIcon; color: string; sub: string }> = {
  rules: { id: 'rules', title: 'Готовые ответы', icon: Zap, color: '#fbbf24', sub: 'без модели' },
  kb: { id: 'kb', title: 'База знаний', icon: BookOpen, color: '#22d3ee', sub: 'поиск + ссылки' },
  agent: {
    id: 'agent',
    title: 'Агент',
    icon: BrainCircuit,
    color: '#a78bfa',
    sub: 'модель выбирает инструменты',
  },
}
const brainOf = (engine: TraceRun['engine']) =>
  engine === 'rules' ? 'rules' : engine === 'kb' ? 'kb' : 'agent'
const fmtMs = (v: number) =>
  v >= 1000 ? (v / 1000).toFixed(1).replace('.', ',') + ' с' : Math.round(v) + ' мс'

export function AgentFlow({ run }: { run: TraceRun }) {
  const [selected, setSelected] = useState<string | null>(null)
  const brain = brainOf(run.engine)
  const toolNames = useMemo(
    () => [
      ...new Set(run.steps.filter((s) => s.kind === 'tool' || s.kind === 'subagent').map((s) => s.name)),
    ],
    [run],
  )

  const frames: Frame[] = useMemo(() => {
    const out: Frame[] = [{ key: 'q', node: 'q', label: 'Вопрос', hold: 600 }]
    let returning: string[] = []
    let brainShown = false
    run.steps.forEach((s, i) => {
      if (s.kind === 'route') {
        out.push({
          key: 'r' + i,
          node: 'router',
          label: 'Маршрут: ' + (s.detail ?? ''),
          ms: s.durMs,
          edges: ['q-router'],
          hold: 900,
        })
        out.push({
          key: 'b' + i,
          node: brain,
          label: BRAIN[brain].title,
          edges: ['router-' + brain],
          hold: 800,
        })
        brainShown = true
      } else if (s.kind === 'llm') {
        const edges = returning.length
          ? returning.map((t) => ({ id: brain + '-' + t, reverse: true }))
          : brainShown
            ? []
            : ['router-' + brain]
        out.push({ key: 'm' + i, node: brain, label: s.label, ms: s.durMs, edges, hold: 1100 })
        brainShown = true
        returning = []
      } else {
        out.push({
          key: 't' + i,
          node: 'tool:' + s.name,
          label: s.name,
          ms: s.durMs,
          status: s.detail === 'ошибка' ? 'error' : 'success',
          edges: [{ id: brain + '-' + s.name, error: s.detail === 'ошибка' }],
          hold: 900,
        })
        returning.push(s.name)
      }
    })
    out.push({
      key: 'answer',
      node: 'answer',
      label: 'Ответ',
      edges:
        brain === 'agent'
          ? [...returning.map((t) => ({ id: brain + '-' + t, reverse: true })), brain + '-answer']
          : returning.length
            ? returning.map((t) => 'tool-' + t + '-answer')
            : [brain + '-answer'],
      status: run.engine === 'none' ? 'retry' : 'success',
      hold: 800,
    })
    return out
  }, [run, brain])
  const replay = useReplay(frames, run.id)

  const y0 = 170
  const toolY = (i: number) => y0 + (i - (toolNames.length - 1) / 2) * 118
  const nodes: FNode[] = [
    {
      id: 'q',
      x: 0,
      y: y0,
      icon: MessageSquareText,
      color: '#a78bfa',
      title: 'Вопрос',
      sub: 'посетитель',
      state: replay.states.q,
    },
    {
      id: 'router',
      x: 220,
      y: y0,
      icon: Split,
      color: '#94a3b8',
      title: 'Маршрутизатор',
      sub: 'самый дешёвый честный путь',
      state: replay.states.router,
    },
    ...Object.values(BRAIN).map((b, i): FNode => ({
      id: b.id,
      x: 470,
      y: y0 + (i - 1) * 150,
      icon: b.icon,
      color: b.color,
      title: b.id === 'agent' && run.engine === 'hermes' ? 'Hermes Agent' : b.title,
      sub: b.id === brain && run.model ? run.model.split('/').pop() : b.sub,
      size: b.id === brain ? 'lg' : 'md',
      state: replay.states[b.id],
      dim: b.id !== brain,
    })),
    ...toolNames.map((t, i): FNode => ({
      id: 'tool:' + t,
      x: 760,
      y: toolY(i),
      icon: TOOL_ICON[t] ?? Wrench,
      color: COLORS[i % COLORS.length],
      title: t,
      sub: fmtMs(run.steps.filter((s) => s.name === t).reduce((a, s) => a + s.durMs, 0)),
      size: 'sm',
      state: replay.states['tool:' + t],
    })),
    {
      id: 'answer',
      x: toolNames.length ? 1040 : 760,
      y: y0,
      icon: FileCheck2,
      color: '#34d399',
      title: 'Ответ',
      sub: `${fmtMs(run.totalMs)} · ${run.costUsd ? '$' + run.costUsd.toFixed(4) : 'бесплатно'}`,
      state: replay.states.answer,
    },
  ]
  const edges: FEdge[] = [
    { id: 'q-router', from: 'q', to: 'router' },
    ...Object.values(BRAIN).map((b) => ({
      id: 'router-' + b.id,
      from: 'router',
      to: b.id,
      dashed: b.id !== brain,
    })),
    ...toolNames.map((t) => ({ id: brain + '-' + t, from: brain, to: 'tool:' + t })),
    ...(brain === 'agent' || !toolNames.length ? [{ id: brain + '-answer', from: brain, to: 'answer' }] : []),
    ...(brain !== 'agent'
      ? toolNames.map((t) => ({ id: 'tool-' + t + '-answer', from: 'tool:' + t, to: 'answer' }))
      : []),
  ]
  const painted = replay.paint(edges)
  const focus = replay.playing ? replay.current?.node : null

  return (
    <div className="fx-console">
      <div className="h-[340px] sm:h-[380px]">
        <FlowCanvas
          nodes={nodes}
          edges={painted}
          focus={focus && toolNames.length > 4 ? focus : null}
          selected={selected}
          onSelect={setSelected}
          scene={run.id + ':' + replay.done}
        />
      </div>
      <Timeline frames={frames} replay={replay} total={run.totalMs} />
    </div>
  )
}
