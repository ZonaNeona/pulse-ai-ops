import { AlertTriangle, Check, Pause, Play, RotateCcw, X } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Frame, useReplay } from './replay'

const fmt = (v?: number) =>
  v === undefined ? '' : v >= 1000 ? (v / 1000).toFixed(1).replace('.', ',') + ' с' : Math.round(v) + ' мс'

export function Timeline({
  frames,
  replay,
  total,
  empty,
}: {
  frames: Frame[]
  replay: ReturnType<typeof useReplay>
  total?: number
  empty?: ReactNode
}) {
  const max = Math.max(1, ...frames.map((f) => f.ms ?? 0))
  return (
    <div className="k-timeline">
      <div className="flex shrink-0 items-center gap-2.5">
        {replay.playing ? (
          <button className="k-play" onClick={replay.pause} aria-label="Пауза">
            <Pause size={15} />
          </button>
        ) : (
          <button className="k-play" onClick={replay.play} disabled={!frames.length} aria-label="Проиграть">
            {replay.done && frames.length ? <RotateCcw size={15} /> : <Play size={15} />}
          </button>
        )}
        <div className="k-tl-total">
          <strong>{total !== undefined ? fmt(total) : '—'}</strong>
          <span>{frames.length ? `${frames.length} шаг.` : 'нет хода'}</span>
        </div>
      </div>
      <div className="k-tl-track">
        {!frames.length && <div className="self-center text-xs text-[var(--k-text3)]">{empty}</div>}
        {frames.map((f, i) => {
          const state =
            i < replay.pos || replay.done ? (f.status ?? 'success') : i === replay.pos ? 'now' : 'todo'
          return (
            <button
              key={f.key}
              className={'k-tl-step ' + state}
              onClick={() => replay.seek(i)}
              title={f.label}
            >
              <span className="k-tl-dot">
                {state === 'success' ? (
                  <Check size={10} strokeWidth={3} />
                ) : state === 'error' ? (
                  <X size={10} strokeWidth={3} />
                ) : state === 'retry' ? (
                  <AlertTriangle size={9} strokeWidth={3} />
                ) : (
                  i + 1
                )}
              </span>
              <span className="k-tl-label">{f.label}</span>
              <span className="k-tl-ms">{fmt(f.ms)}</span>
              <span className="k-tl-bar">
                <i style={{ width: Math.max(4, ((f.ms ?? 0) / max) * 100) + '%' }} />
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
