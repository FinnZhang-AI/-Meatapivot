/// <reference types="vitest" />
// @vitest-environment jsdom

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// jsdom should ship localStorage, but in case it doesn't (older jsdom
// versions, or sandboxed envs), make sure we have a working stub
// before the component under test reads it.
if (typeof window !== 'undefined' && !window.localStorage) {
  const memStore: Record<string, string> = {}
  Object.defineProperty(window, 'localStorage', {
    value: {
      getItem: (k: string) => memStore[k] ?? null,
      setItem: (k: string, v: string) => { memStore[k] = String(v) },
      removeItem: (k: string) => { delete memStore[k] },
      clear: () => { for (const k of Object.keys(memStore)) delete memStore[k] },
      key: (i: number) => Object.keys(memStore)[i] ?? null,
      get length() { return Object.keys(memStore).length },
    },
  })
}

// We mock the auth hook because GlobalSearch reads user/token from it
// and we don't want to set up a real AuthProvider for these tests.
const mockAuth = { user: { id: 'u1', tenant_id: 't1' }, token: 'tok' }
vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockAuth,
}))

let fetchMock: ReturnType<typeof vi.fn>
beforeEach(() => {
  fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ suggestions: [], count: 0, query: '' }),
  })
  ;(globalThis as any).fetch = fetchMock
  if (typeof window !== 'undefined' && window.localStorage) {
    window.localStorage.clear()
  }
})
afterEach(() => {
  vi.useRealTimers()
})

import GlobalSearch from '../components/GlobalSearch'

function renderSearch() {
  return render(
    <MemoryRouter>
      <GlobalSearch />
    </MemoryRouter>
  )
}

describe('GlobalSearch', () => {
  it('renders the search input + mode selector', () => {
    renderSearch()
    const input = screen.getByPlaceholderText('全局搜索...')
    expect(input).toBeInTheDocument()
    const select = screen.getByLabelText('搜索模式') as HTMLSelectElement
    expect(select.options.length).toBe(3)
    expect(select.value).toBe('semantic')
  })

  it('persists a submitted query to per-user localStorage history', async () => {
    vi.useFakeTimers()
    renderSearch()
    const input = screen.getByPlaceholderText('全局搜索...') as HTMLInputElement
    const form = input.closest('form') as HTMLFormElement
    expect(form).toBeTruthy()
    await act(async () => {
      fireEvent.change(input, { target: { value: 'employee' } })
      fireEvent.submit(form)
    })
    const raw = window.localStorage.getItem('meatapivot:search-history:u1')
    expect(raw).toBeTruthy()
    const entries = JSON.parse(raw || '[]')
    expect(entries[0]?.query).toBe('employee')
    expect(entries[0]?.mode).toBe('semantic')
  })
})
