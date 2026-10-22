import { useSyncExternalStore } from 'react'

export type Theme = 'light' | 'dark'
const KEY = 'pulse-theme'
const listeners = new Set<() => void>()

function stored(): Theme | null {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null
  }
}

function system(): Theme {
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function currentTheme(): Theme {
  return (document.documentElement.dataset.theme as Theme | undefined) ?? 'light'
}

export function applyTheme(theme: Theme, persist = false) {
  document.documentElement.dataset.theme = theme
  if (persist) {
    try {
      localStorage.setItem(KEY, theme)
    } catch {
      /* private mode: the choice lasts for this page only */
    }
  }
  listeners.forEach((l) => l())
}

/** Call once before the first render, so the page never flashes the wrong theme. */
export function initTheme() {
  applyTheme(stored() ?? system())
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (!stored()) applyTheme(system())
  })
}

export function useTheme(): [Theme, () => void] {
  const theme = useSyncExternalStore((cb) => {
    listeners.add(cb)
    return () => listeners.delete(cb)
  }, currentTheme)
  return [theme, () => applyTheme(theme === 'dark' ? 'light' : 'dark', true)]
}
