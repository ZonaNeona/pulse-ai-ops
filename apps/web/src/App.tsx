import { lazy, Suspense, useEffect, type ComponentType } from 'react'
import { Shell } from '@/app/Shell'
import { navigate, useRoute } from '@/app/router'
import { updateBackButton } from '@/app/telegram'
import { Overview } from '@/screens/Overview'
import { Empty, Skeleton } from '@/ui/kit'

// The overview is the landing screen and ships in the main chunk; the rest load on first visit.
// A tab opened before a release asks for chunks the new release no longer has: reload once to get the new ones.
function screen<T>(load: () => Promise<T>, pick: (m: T) => ComponentType) {
  return lazy(() =>
    load()
      .then((m) => {
        sessionStorage.removeItem('pulse-reloaded')
        return { default: pick(m) }
      })
      .catch((err: unknown) => {
        if (!sessionStorage.getItem('pulse-reloaded')) {
          sessionStorage.setItem('pulse-reloaded', '1')
          location.reload()
        }
        throw err
      }),
  )
}
const Sales = screen(
  () => import('@/screens/Sales'),
  (m) => m.Sales,
)
const Documents = screen(
  () => import('@/screens/Documents'),
  (m) => m.Documents,
)
const Knowledge = screen(
  () => import('@/screens/Knowledge'),
  (m) => m.Knowledge,
)
const Integrations = screen(
  () => import('@/screens/Integrations'),
  (m) => m.Integrations,
)
const Copilot = screen(
  () => import('@/screens/Copilot'),
  (m) => m.Copilot,
)
const UnderTheHood = screen(
  () => import('@/screens/UnderTheHood'),
  (m) => m.UnderTheHood,
)
const HowWeWork = screen(
  () => import('@/screens/HowWeWork'),
  (m) => m.HowWeWork,
)
const Roadmap = screen(
  () => import('@/screens/Roadmap'),
  (m) => m.Roadmap,
)
const Quality = screen(
  () => import('@/screens/Quality'),
  (m) => m.QualityScreen,
)
const DesignSystem = screen(
  () => import('@/screens/DesignSystem'),
  (m) => m.DesignSystem,
)

function Screen({ path }: { path: string }) {
  if (path === '/') return <Overview />
  if (path === '/sales' || path.startsWith('/sales/')) return <Sales />
  if (path === '/docs') return <Documents />
  if (path === '/knowledge') return <Knowledge />
  if (path === '/integrations') return <Integrations />
  if (path === '/copilot') return <Copilot />
  if (path === '/under-the-hood') return <UnderTheHood />
  if (path === '/work') return <HowWeWork />
  if (path === '/work/roadmap') return <Roadmap />
  if (path === '/work/quality') return <Quality />
  if (path === '/design') return <DesignSystem />
  return <Empty title="Страница не найдена" text="Проверьте адрес или откройте обзор" />
}

function Loading() {
  return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-14 w-80" />
      <Skeleton className="h-64" />
    </div>
  )
}

export default function App() {
  const { path } = useRoute()

  useEffect(() => {
    updateBackButton(path !== '/', () => navigate('/'))
  }, [path])

  return (
    <Shell>
      <Suspense fallback={<Loading />}>
        <Screen path={path} />
      </Suspense>
    </Shell>
  )
}
