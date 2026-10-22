// Replays a recorded run frame by frame: lights nodes, sends particles along edges, moves the camera.
// Durations shown are the real ones from the run; the replay itself is paced for the eye.
import { useEffect, useMemo, useState } from 'react'
import type { FEdge, RunState } from './FlowCanvas'

export interface Frame {
  key: string
  node: string
  edges?: (string | { id: string; reverse?: boolean; error?: boolean })[]
  status?: 'success' | 'error' | 'retry'
  label: string
  /** Real duration of the step. */
  ms?: number
  /** How long the replay shows the frame. */
  hold?: number
}

export function useReplay(frames: Frame[], key: string, autoplay = true) {
  const [pos, setPos] = useState(frames.length)
  const [playing, setPlaying] = useState(false)
  useEffect(() => {
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (autoplay && !reduced && frames.length) {
      setPos(0)
      setPlaying(true)
    } else {
      setPos(frames.length)
      setPlaying(false)
    }
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!playing) return
    if (pos >= frames.length) {
      setPlaying(false)
      return
    }
    const t = setTimeout(() => setPos((p) => p + 1), frames[pos].hold ?? 1000)
    return () => clearTimeout(t)
  }, [playing, pos, frames])

  const view = useMemo(() => {
    const states: Record<string, RunState> = {}
    const lit = new Set<string>()
    const pulses: Record<string, { pulse: number; reverse?: boolean; error?: boolean }> = {}
    frames.slice(0, Math.min(pos + 1, frames.length)).forEach((f, i) => {
      const current = i === pos && pos < frames.length
      states[f.node] = current && playing ? 'running' : (f.status ?? 'success')
      for (const e of f.edges ?? []) {
        const id = typeof e === 'string' ? e : e.id
        lit.add(id)
        if (current)
          pulses[id] = {
            pulse: i + 1,
            reverse: typeof e === 'string' ? false : e.reverse,
            error: typeof e === 'string' ? false : e.error,
          }
      }
    })
    return { states, lit, pulses }
  }, [frames, pos, playing])

  return {
    pos,
    playing,
    current: pos < frames.length ? frames[pos] : null,
    done: pos >= frames.length,
    play: () => {
      if (pos >= frames.length) setPos(0)
      setPlaying(true)
    },
    pause: () => setPlaying(false),
    seek: (i: number) => {
      setPlaying(false)
      setPos(i)
    },
    ...view,
    paint: (edges: FEdge[]): FEdge[] =>
      edges.map((e) => ({
        ...e,
        lit: view.lit.has(e.id) || e.lit,
        pulse: view.pulses[e.id]?.pulse,
        reverse: view.pulses[e.id]?.reverse,
        error: view.pulses[e.id]?.error || e.error,
      })),
  }
}
