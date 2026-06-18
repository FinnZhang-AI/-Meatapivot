import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// Stub the auth + API helpers so the component renders without a
// real backend. The goal of this test is to verify the surface — the
// input, the budget banner, the summary cards, the CSV button — not
// the network shape (covered by the hook tests).
const mockUser = { id: 'u1', tenant_id: 't1' }
const mockToken = 'tok'

// useAuth is a .tsx file; mock by its full module path so the resolver
// doesn't get confused by the extension.
vi.mock('../../hooks/useAuth.tsx', () => ({
  useAuth: () => ({ user: mockUser, token: mockToken }),
}))

const mockReport = {
  tenantId: 't1',
  days: 30,
  groupBy: 'day' as const,
  totalCalls: 42,
  totalTokens: 12345,
  totalCostCents: 250,
  byModel: [
    { model: 'gpt-4o', callCount: 30, totalTokens: 10000, estimatedCostCents: 200 },
    { model: 'claude-3-5-sonnet', callCount: 12, totalTokens: 2345, estimatedCostCents: 50 },
  ],
  trend: [
    { bucket: '2026-06-15T00:00', callCount: 5, totalTokens: 1000, estimatedCostCents: 20 },
    { bucket: '2026-06-15T01:00', callCount: 8, totalTokens: 2000, estimatedCostCents: 40 },
  ],
  budget: null,
  budgetState: 'no_budget' as const,
}

vi.mock('../../hooks/useLLMCost', () => ({
  useLLMCostReport: () => ({ data: mockReport, isLoading: false, error: null }),
  useLLMBudget: () => ({ data: null }),
  useUpsertBudget: () => ({ mutateAsync: vi.fn() }),
  downloadCostCsv: vi.fn(),
}))

import CostDashboard from './CostDashboard'

beforeEach(() => {
  if (typeof window !== 'undefined' && window.localStorage) {
    window.localStorage.clear()
  }
})
afterEach(() => {
  vi.useRealTimers()
})

function renderDashboard() {
  return render(
    <MemoryRouter>
      <CostDashboard />
    </MemoryRouter>
  )
}

describe('CostDashboard', () => {
  it('renders the three summary cards with the report totals', () => {
    renderDashboard()
    // 250 cents → $2.50
    expect(screen.getByText(/\$2\.50/)).toBeInTheDocument()
    // 42 total calls
    expect(screen.getByText('42')).toBeInTheDocument()
    // 12,345 total tokens
    expect(screen.getByText('12,345')).toBeInTheDocument()
  })

  it('shows the "no budget" banner when no budget is set', () => {
    renderDashboard()
    expect(screen.getByText('未设置预算')).toBeInTheDocument()
  })

  it('renders a row per model in the detail table', () => {
    renderDashboard()
    // 2 models in the mock report
    const tableRows = document.querySelectorAll('tbody tr')
    expect(tableRows.length).toBe(2)
  })

  it('has a CSV export button', () => {
    renderDashboard()
    expect(screen.getByText('导出 CSV')).toBeInTheDocument()
  })

  it('opens the budget editor when the user clicks "设置预算"', async () => {
    renderDashboard()
    const setupButton = screen.getByText('设置预算')
    fireEvent.click(setupButton)
    await waitFor(() => {
      // The editor swaps in a form with a number input + "保存" button
      expect(screen.getByText('保存')).toBeInTheDocument()
    })
  })
})
