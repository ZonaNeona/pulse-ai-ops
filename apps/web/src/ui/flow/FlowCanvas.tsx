// Animated canvas for automations, ported from the owner's earlier demo: custom nodes, particles along the
// edges, the camera follows the active step while a run is replayed. Positions are given in a landscape
// layout and turned top-to-bottom on narrow screens.
import '@xyflow/react/dist/base.css'
import './flow.css'
import { Fragment, memo, useEffect, useMemo, useRef, type CSSProperties } from 'react'
import {
  Background,
  BackgroundVariant,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  getBezierPath,
  getViewportForBounds,
  useReactFlow,
  useStore,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import { Check, Lock, RotateCw, X, type LucideIcon } from 'lucide-react'

export type RunState = 'idle' | 'wait' | 'running' | 'success' | 'error' | 'retry' | 'locked'
export type Side = 'l' | 'r' | 't' | 'b'

export interface FNode {
  id: string
  x: number
  y: number
  icon: LucideIcon
  color: string
  title: string
  sub?: string
  state?: RunState
  badge?: string | number
  size?: 'lg' | 'md' | 'sm'
  dim?: boolean
}

export interface FEdge {
  id: string
  from: string
  to: string
  out?: Side
  in?: Side
  /** A new value starts a new particle. */
  pulse?: number
  reverse?: boolean
  error?: boolean
  /** Already passed in the current run. */
  lit?: boolean
  dashed?: boolean
  /** Running dash: work in progress. */
  flow?: boolean
  label?: string
}

type ND = FNode & { selected: boolean } & Record<string, unknown>
type ED = Omit<FEdge, 'id' | 'from' | 'to' | 'out' | 'in'> & Record<string, unknown>

const SIZE = { lg: 72, md: 60, sm: 46 }
const pos: Record<Side, Position> = {
  l: Position.Left,
  r: Position.Right,
  t: Position.Top,
  b: Position.Bottom,
}

const FlowNode = memo(function FlowNode({ data }: NodeProps<Node<ND>>) {
  const Icon = data.icon
  const state = data.state ?? 'idle'
  const px = SIZE[data.size ?? 'md']
  return (
    <div
      className={`fx-node fx-${state} ${data.selected ? 'fx-selected' : ''} ${data.dim ? 'fx-dim' : ''}`}
      style={{ '--c': data.color, width: Math.max(px + 60, 124) } as CSSProperties}
    >
      <div className="fx-tile" style={{ width: px, height: px }}>
        {(['l', 'r', 't', 'b'] as Side[]).map((s) => (
          <Fragment key={s}>
            <Handle id={'t' + s} type="target" position={pos[s]} />
            <Handle id={'s' + s} type="source" position={pos[s]} />
          </Fragment>
        ))}
        <Icon size={Math.round(px * 0.38)} strokeWidth={1.7} />
        {(state === 'success' || state === 'error' || state === 'retry' || state === 'locked') && (
          <span className="fx-mark">
            {state === 'success' ? (
              <Check size={12} strokeWidth={3} />
            ) : state === 'error' ? (
              <X size={12} strokeWidth={3} />
            ) : state === 'locked' ? (
              <Lock size={11} strokeWidth={2.6} />
            ) : (
              <RotateCw size={11} strokeWidth={3} />
            )}
          </span>
        )}
        {data.badge !== undefined && <span className="fx-badge">{data.badge}</span>}
      </div>
      <div className="fx-title">{data.title}</div>
      {data.sub && <div className="fx-sub">{data.sub}</div>}
    </div>
  )
})

function FlowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps<Edge<ED>>) {
  const [path, lx, ly] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    curvature: 0.32,
  })
  const lit = data?.lit || !!data?.pulse
  const err = data?.error
  const motion = data?.reverse ? { keyPoints: '1;0', keyTimes: '0;1', calcMode: 'linear' as const } : {}
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        className={`fx-edge ${lit ? 'lit' : ''} ${err ? 'err' : ''} ${data?.dashed ? 'dashed' : ''} ${data?.flow ? 'flow' : ''}`}
      />
      {!!data?.pulse && (
        <g key={data.pulse}>
          {/* r=0 until the start, otherwise the dot flashes at the origin */}
          <circle r={0} className={`fx-particle ${err ? 'err' : ''}`}>
            <set attributeName="r" to="4.5" begin="0s" fill="freeze" />
            <animateMotion dur="0.75s" repeatCount="1" fill="freeze" path={path} {...motion} />
          </circle>
          <circle r={0} className={`fx-particle trail ${err ? 'err' : ''}`}>
            <set attributeName="r" to="2.5" begin="0.09s" fill="freeze" />
            <animateMotion dur="0.75s" begin="0.09s" repeatCount="1" fill="freeze" path={path} {...motion} />
          </circle>
        </g>
      )}
      {data?.label && (
        <EdgeLabelRenderer>
          <div
            className={`fx-edge-label nodrag nopan ${lit ? 'lit' : ''} ${err ? 'err' : ''}`}
            style={{ transform: `translate(-50%,-50%) translate(${lx}px,${ly}px)` }}
          >
            {data.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

const nodeTypes = { fx: FlowNode }
const edgeTypes = { fx: FlowEdge }

export interface CanvasProps {
  nodes: FNode[]
  edges: FEdge[]
  /** The node the camera follows; null — the whole scheme. */
  focus?: string | null
  selected?: string | null
  onSelect?: (id: string | null) => void
  /** Scene key: when it changes the camera fits the scheme again. */
  scene?: string
  zoom?: number
}

function Canvas(p: CanvasProps) {
  const { setViewport, setCenter } = useReactFlow()
  const width = useStore((s) => s.width)
  const height = useStore((s) => s.height)
  const first = useRef(true)
  const vertical = width > 0 && width < 640
  const at = (n: FNode) => (vertical ? { x: n.y * 0.85, y: n.x * 0.62 } : { x: n.x, y: n.y })
  const side = (s: Side): Side => (vertical ? ({ l: 't', r: 'b', t: 'l', b: 'r' } as const)[s] : s)

  const nodes: Node<ND>[] = useMemo(
    () =>
      p.nodes.map((n) => ({
        id: n.id,
        type: 'fx',
        position: at(n),
        draggable: false,
        data: { ...n, selected: p.selected === n.id },
      })),
    [p.nodes, p.selected, vertical], // eslint-disable-line react-hooks/exhaustive-deps
  )
  const edges: Edge<ED>[] = useMemo(
    () =>
      p.edges.map(({ id, from, to, out, in: inn, ...data }) => ({
        id,
        source: from,
        target: to,
        sourceHandle: 's' + side(out ?? 'r'),
        targetHandle: 't' + side(inn ?? 'l'),
        type: 'fx',
        data,
      })),
    [p.edges, vertical], // eslint-disable-line react-hooks/exhaustive-deps
  )

  useEffect(() => {
    if (!width || !height || !p.nodes.length) return
    const n = p.focus ? p.nodes.find((x) => x.id === p.focus) : null
    const duration = first.current ? 0 : 650
    first.current = false
    if (n) {
      const c = at(n)
      void setCenter(c.x + 62, c.y + 48, { zoom: vertical ? 0.8 : 1, duration: 600 })
      return
    }
    const pts = p.nodes.map(at)
    const xs = pts.map((q) => q.x)
    const ys = pts.map((q) => q.y)
    const bounds = {
      x: Math.min(...xs) - 30,
      y: Math.min(...ys) - 40,
      width: Math.max(...xs) - Math.min(...xs) + 190,
      height: Math.max(...ys) - Math.min(...ys) + 170,
    }
    void setViewport(getViewportForBounds(bounds, width, height, 0.2, p.zoom ?? 1.05, 0.04), { duration })
  }, [width, height, vertical, p.focus, p.scene]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      minZoom={0.2}
      maxZoom={1.8}
      nodesConnectable={false}
      elementsSelectable
      panOnScroll={false}
      zoomOnScroll={false}
      preventScrolling={false}
      proOptions={{ hideAttribution: true }}
      onNodeClick={(_, n) => p.onSelect?.(n.id)}
      onPaneClick={() => p.onSelect?.(null)}
    >
      <Background variant={BackgroundVariant.Dots} gap={22} size={1.3} color="var(--k-dots)" />
      <Controls showInteractive={false} position="bottom-left" />
    </ReactFlow>
  )
}

export function FlowCanvas(props: CanvasProps & { className?: string }) {
  return (
    <div className={`fx-canvas ${props.className ?? ''}`}>
      <ReactFlowProvider>
        <Canvas {...props} />
      </ReactFlowProvider>
    </div>
  )
}
