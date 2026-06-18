import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ValidationToaster from '../components/ValidationToaster'
import type { InterfaceValidationReport } from '../hooks/useInterfaceValidationWS'

function renderToaster() {
  return render(
    <MemoryRouter>
      <ValidationToaster />
    </MemoryRouter>
  )
}

function fireValidationEvent(detail: InterfaceValidationReport) {
  window.dispatchEvent(
    new CustomEvent('meatapivot:interface-validation', { detail })
  )
}

describe('ValidationToaster', () => {
  it('renders nothing before any event', () => {
    renderToaster()
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('shows a green toast on completed / no failures', async () => {
    renderToaster()
    fireValidationEvent({
      status: 'completed',
      tenant_id: 't1',
      interfaces_total: 3,
      interfaces_failed: 0,
      results: [],
      completed_at: '2026-06-16T00:00:00.000Z',
    })
    const toast = await screen.findByRole('status')
    expect(toast.textContent).toMatch(/全部通过/)
  })

  it('shows a red toast when some interface failed', async () => {
    renderToaster()
    fireValidationEvent({
      status: 'completed',
      tenant_id: 't1',
      interfaces_total: 3,
      interfaces_failed: 1,
      results: [],
      completed_at: undefined,
    })
    const toast = await screen.findByRole('status')
    expect(toast.textContent).toMatch(/1 \/ 3 个存在不一致/)
  })

  it('shows a red toast on failed status', async () => {
    renderToaster()
    fireValidationEvent({
      status: 'failed',
      tenant_id: 't1',
      error: 'db connection lost',
      completed_at: undefined,
    })
    const toast = await screen.findByRole('status')
    expect(toast.textContent).toMatch(/失败.*db connection lost/)
  })

  it('shows a blue toast when the tenant has no interfaces', async () => {
    renderToaster()
    fireValidationEvent({
      status: 'completed',
      tenant_id: 't1',
      interfaces_total: 0,
      interfaces_failed: 0,
      results: [],
      completed_at: undefined,
    })
    const toast = await screen.findByRole('status')
    expect(toast.textContent).toMatch(/没有 Interface/)
  })
})
