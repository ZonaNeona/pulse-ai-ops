import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import App from './App'
import { BUDGET, OVERVIEW } from './mock/demo'
import { plural, rubShort } from './ui/format'

const RESPONSES: Record<string, unknown> = { '/api/overview': OVERVIEW, '/api/budget': BUDGET }

beforeAll(() => {
  window.matchMedia ??= (() => ({ matches: false, addEventListener() {}, removeEventListener() {} })) as never
  vi.stubGlobal('fetch', (url: string) =>
    Promise.resolve(
      new Response(JSON.stringify(RESPONSES[url] ?? {}), { status: url in RESPONSES ? 200 : 404 }),
    ),
  )
})

test('overview renders module health and the action feed', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>,
  )
  expect(await screen.findByText('Обзор компании')).toBeInTheDocument()
  expect(await screen.findByText('Сделать сейчас')).toBeInTheDocument()
})

test('russian plurals and short money', () => {
  expect(plural(1, ['звонок', 'звонка', 'звонков'])).toBe('звонок')
  expect(plural(3, ['звонок', 'звонка', 'звонков'])).toBe('звонка')
  expect(plural(12, ['звонок', 'звонка', 'звонков'])).toBe('звонков')
  expect(rubShort(2_400_000)).toBe('2,4 млн ₽')
})
