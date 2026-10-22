import clsx from 'clsx'
import { Menu, Moon, Search, Sun } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState, type ReactNode } from 'react'
import { useBudget, useOverview } from '@/api/queries'
import { Meter } from '@/ui/charts'
import { usd } from '@/ui/format'
import { GithubIcon } from '@/ui/icons'
import { IconButton, Kbd } from '@/ui/kit'
import { CommandPalette } from './CommandPalette'
import { activeNav, GITHUB_URL, NAV, type NavItem } from './nav'
import { navigate, useRoute } from './router'
import { useTheme } from './theme'

function Logo() {
  return (
    <div className="flex items-center gap-2">
      <svg viewBox="0 0 32 32" className="size-6" aria-hidden>
        <rect width="32" height="32" rx="8" fill="var(--accent)" />
        <path
          d="M5 17h5l3-7 5 13 3-6h6"
          fill="none"
          stroke="var(--accent-fg)"
          strokeWidth="2.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="text-base font-semibold tracking-[-0.02em] text-ink">Пульс</span>
    </div>
  )
}

function NavLink({ item, active, onClick }: { item: NavItem; active: boolean; onClick: () => void }) {
  return (
    <a
      href={'#' + item.path}
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
      className={clsx(
        'group flex h-8 items-center gap-2.5 rounded-md px-2.5 text-sm font-medium transition-colors duration-150',
        active ? 'bg-surface text-ink shadow-card' : 'text-muted hover:bg-surface-2 hover:text-ink',
      )}
    >
      <item.icon size={16} className={active ? 'text-accent' : 'text-faint group-hover:text-muted'} />
      <span className="flex-1">{item.label}</span>
      {item.soon && <span className="rounded-sm bg-surface-2 px-1 text-[10px] font-medium text-faint">скоро</span>}
    </a>
  )
}

function Sidebar({ path, onNavigate, onSearch }: { path: string; onNavigate: () => void; onSearch: () => void }) {
  const [theme, toggleTheme] = useTheme()
  const current = activeNav(path)
  const { data: overview } = useOverview()
  const { data: budget } = useBudget()
  const groups: [NavItem['group'], string | null][] = [
    ['main', null],
    ['ai', 'ИИ-слой'],
    ['meta', 'Проект'],
  ]
  return (
    <div className="flex h-full flex-col gap-4 px-3 py-4">
      <div className="flex items-center justify-between px-1.5">
        <Logo />
        <IconButton label={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'} onClick={toggleTheme}>
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </IconButton>
      </div>

      <div className="rounded-lg border border-line bg-surface px-3 py-2.5 shadow-card">
        <div className="text-sm font-medium text-ink">{overview?.company.name ?? 'Демо-компания'}</div>
        <div className="mt-0.5 truncate text-xs text-muted">{overview?.company.industry ?? '…'}</div>
      </div>

      <button
        onClick={onSearch}
        className="flex h-8 items-center gap-2 rounded-md border border-line bg-surface px-2.5 text-sm text-faint shadow-card transition-colors hover:text-muted"
      >
        <Search size={14} />
        <span className="flex-1 text-left">Поиск и команды</span>
        <Kbd>⌘K</Kbd>
      </button>

      <nav className="flex flex-col gap-4">
        {groups.map(([group, title]) => (
          <div key={group} className="flex flex-col gap-0.5">
            {title && <div className="px-2.5 pb-1 text-xs font-medium text-faint">{title}</div>}
            {NAV.filter((n) => n.group === group).map((n) => (
              <NavLink key={n.path} item={n} active={current?.path === n.path} onClick={onNavigate} />
            ))}
          </div>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-3">
        <a
          href="#/under-the-hood"
          onClick={onNavigate}
          className="rounded-lg border border-line bg-surface px-3 py-2.5 shadow-card"
        >
          <div className="text-xs text-muted">Бюджет ИИ сегодня</div>
          <div className="num mt-0.5 text-sm font-medium text-ink">
            {usd(budget?.spentUsd ?? 0)} <span className="font-normal text-muted">из {usd(budget?.capUsd ?? 0)}</span>
          </div>
          <Meter value={budget?.spentUsd ?? 0} max={budget?.capUsd ?? 1} className="mt-2" />
        </a>
        <div className="flex items-center justify-between px-1.5 text-xs text-faint">
          <span>Данные вымышлены, сброс каждую ночь</span>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer" aria-label="Код на GitHub" className="hover:text-ink">
            <GithubIcon size={15} />
          </a>
        </div>
      </div>
    </div>
  )
}

export function Shell({ children }: { children: ReactNode }) {
  const { path } = useRoute()
  const [palette, setPalette] = useState(false)
  const [drawer, setDrawer] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPalette((v) => !v)
      } else if (e.key === 'Escape') setDrawer(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    setDrawer(false)
    window.scrollTo({ top: 0 })
  }, [path])

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-screen border-r border-line lg:block">
        <Sidebar path={path} onNavigate={() => {}} onSearch={() => setPalette(true)} />
      </aside>

      <header className="sticky top-0 z-30 flex h-12 items-center justify-between border-b border-line bg-bg/85 px-4 backdrop-blur lg:hidden">
        <IconButton label="Меню" onClick={() => setDrawer(true)}>
          <Menu size={18} />
        </IconButton>
        <button onClick={() => navigate('/')} aria-label="На главную">
          <Logo />
        </button>
        <IconButton label="Поиск" onClick={() => setPalette(true)}>
          <Search size={16} />
        </IconButton>
      </header>

      <AnimatePresence>
        {drawer && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <motion.div
              className="absolute inset-0 bg-black/30"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setDrawer(false)}
            />
            <motion.aside
              className="absolute inset-y-0 left-0 w-[280px] border-r border-line bg-bg"
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            >
              <Sidebar path={path} onNavigate={() => setDrawer(false)} onSearch={() => setPalette(true)} />
            </motion.aside>
          </div>
        )}
      </AnimatePresence>

      <main className="min-w-0 px-4 py-5 sm:px-6 lg:px-8 lg:py-7">
        <div className="mx-auto max-w-[1240px]">{children}</div>
      </main>

      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </div>
  )
}
