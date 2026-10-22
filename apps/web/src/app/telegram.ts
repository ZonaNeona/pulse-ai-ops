/** Telegram Mini App (TMA / WebApp) bridge: theme, back button, haptics, initData session. */

import { applyTheme, type Theme } from './theme'

export interface TgUser {
  id: number
  first_name: string
  last_name?: string
  username?: string
  language_code?: string
}

export interface TelegramWebApp {
  initData: string
  initDataUnsafe: {
    query_id?: string
    user?: TgUser
    auth_date?: number
    hash?: string
  }
  version: string
  platform: string
  colorScheme: 'light' | 'dark'
  themeParams: Record<string, string>
  isExpanded: boolean
  viewportHeight: number
  viewportStableHeight: number
  headerColor: string
  backgroundColor: string
  BackButton: {
    isVisible: boolean
    show: () => void
    hide: () => void
    onClick: (cb: () => void) => void
    offClick: (cb: () => void) => void
  }
  MainButton: {
    text: string
    color: string
    textColor: string
    isVisible: boolean
    isActive: boolean
    show: () => void
    hide: () => void
    enable: () => void
    disable: () => void
    onClick: (cb: () => void) => void
    offClick: (cb: () => void) => void
  }
  HapticFeedback: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void
    notificationOccurred: (type: 'error' | 'success' | 'warning') => void
    selectionChanged: () => void
  }
  ready: () => void
  expand: () => void
  close: () => void
  onEvent: (eventType: string, cb: () => void) => void
  offEvent: (eventType: string, cb: () => void) => void
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp
    }
  }
}

export function getTelegramWebApp(): TelegramWebApp | null {
  if (typeof window === 'undefined') return null
  return window.Telegram?.WebApp ?? null
}

export function isTelegramMiniApp(): boolean {
  const tg = getTelegramWebApp()
  return Boolean(tg && tg.initData)
}

export function haptic(type: 'light' | 'medium' | 'heavy' | 'success' | 'warning' | 'error' = 'medium') {
  const tg = getTelegramWebApp()
  if (!tg?.HapticFeedback) return
  try {
    if (type === 'success' || type === 'warning' || type === 'error') {
      tg.HapticFeedback.notificationOccurred(type)
    } else {
      tg.HapticFeedback.impactOccurred(type)
    }
  } catch {
    // ignore
  }
}

let backButtonHandler: (() => void) | null = null

export function updateBackButton(canGoBack: boolean, onBack: () => void) {
  const tg = getTelegramWebApp()
  if (!tg?.BackButton) return

  if (backButtonHandler) {
    tg.BackButton.offClick(backButtonHandler)
    backButtonHandler = null
  }

  if (canGoBack) {
    backButtonHandler = () => {
      haptic('light')
      onBack()
    }
    tg.BackButton.onClick(backButtonHandler)
    tg.BackButton.show()
  } else {
    tg.BackButton.hide()
  }
}

/** Initializes the Telegram WebApp environment: expands to full screen, synchronizes theme and user session. */
export function initTelegram() {
  const tg = getTelegramWebApp()
  if (!tg) return

  try {
    tg.ready()
    tg.expand()

    // 1. Theme sync with Telegram app
    const syncTheme = () => {
      const tgScheme = tg.colorScheme as Theme | undefined
      if (tgScheme === 'dark' || tgScheme === 'light') {
        applyTheme(tgScheme, false)
      }
    }
    syncTheme()
    tg.onEvent('themeChanged', syncTheme)

    // 2. Synchronize user session: bind visitor ID to Telegram user ID for shared state
    const user = tg.initDataUnsafe?.user
    if (user?.id) {
      const tgVisitorId = `tg_${user.id}`
      try {
        localStorage.setItem('pulse_visitor_id', tgVisitorId)
      } catch {
        // ignore
      }
    }
  } catch {
    // non-telegram browser fallback
  }
}
