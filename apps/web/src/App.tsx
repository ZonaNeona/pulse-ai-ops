import { lazy, Suspense } from 'react'
import { Shell } from '@/app/Shell'
import { useRoute } from '@/app/router'
import { Overview } from '@/screens/Overview'
import { Empty, Skeleton } from '@/ui/kit'

// The overview is the landing screen and ships in the main chunk; the rest load on first visit.
const Sales = lazy(() => import('@/screens/Sales').then((m) => ({ default: m.Sales })))
const Documents = lazy(() => import('@/screens/Documents').then((m) => ({ default: m.Documents })))
const Knowledge = lazy(() => import('@/screens/Knowledge').then((m) => ({ default: m.Knowledge })))
const Integrations = lazy(() => import('@/screens/Integrations').then((m) => ({ default: m.Integrations })))
const Copilot = lazy(() => import('@/screens/Copilot').then((m) => ({ default: m.Copilot })))
const UnderTheHood = lazy(() => import('@/screens/UnderTheHood').then((m) => ({ default: m.UnderTheHood })))
const DesignSystem = lazy(() => import('@/screens/DesignSystem').then((m) => ({ default: m.DesignSystem })))

function Screen({ path }: { path: string }) {
  if (path === '/') return <Overview />
  if (path === '/sales' || path.startsWith('/sales/')) return <Sales />
  if (path === '/docs') return <Documents />
  if (path === '/knowledge') return <Knowledge />
  if (path === '/integrations') return <Integrations />
  if (path === '/copilot') return <Copilot />
  if (path === '/under-the-hood') return <UnderTheHood />
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
  return (
    <Shell>
      <Suspense fallback={<Loading />}>
        <Screen path={path} />
      </Suspense>
    </Shell>
  )
}
