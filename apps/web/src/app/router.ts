// Minimal hash router with a depth counter, so Telegram's BackButton knows whether there is history.
// The query lives inside the hash (#/sales/calls?id=12) and never touches the URL Telegram launched.
import { useMemo, useSyncExternalStore } from 'react'

const listeners = new Set<() => void>()
let depth: number = history.state && typeof history.state.depth === 'number' ? history.state.depth : 0

const emit = () => listeners.forEach((l) => l())
window.addEventListener('popstate', (e) => {
  depth = e.state && typeof e.state.depth === 'number' ? e.state.depth : 0
  emit()
})
window.addEventListener('hashchange', emit)

export function navigate(to: string, opts: { replace?: boolean } = {}) {
  if (opts.replace) history.replaceState({ depth }, '', '#' + to)
  else {
    depth += 1
    history.pushState({ depth }, '', '#' + to)
  }
  emit()
}

export function back(fallback = '/') {
  if (depth > 0) history.back()
  else {
    history.replaceState({ depth: 0 }, '', '#' + fallback)
    emit()
  }
}

export const canGoBack = () => depth > 0

function subscribe(cb: () => void) {
  listeners.add(cb)
  return () => {
    listeners.delete(cb)
  }
}

export function parse(hash: string) {
  const raw = hash.replace(/^#/, '')
  if (!raw.startsWith('/')) return { path: '/', query: new URLSearchParams() }
  const [path, query = ''] = raw.split('?')
  return { path: path || '/', query: new URLSearchParams(query) }
}

export function useRoute() {
  const hash = useSyncExternalStore(subscribe, () => location.hash)
  return useMemo(() => parse(hash), [hash])
}

export function withQuery(path: string, query: Record<string, string | null | undefined>) {
  const q = new URLSearchParams()
  Object.entries(query).forEach(([k, v]) => {
    if (v) q.set(k, v)
  })
  const s = q.toString()
  return s ? `${path}?${s}` : path
}
