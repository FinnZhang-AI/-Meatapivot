import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

// Mock the run hook before importing the component under test, so the
// editor receives a controlled implementation we can flip per-case.
const runMock = vi.fn()
const hookState: {
  run: typeof runMock
  isLoading: boolean
  error: Error | null
  executions: unknown[]
  currentExecution: unknown
  refetch: () => void
} = {
  run: runMock,
  isLoading: false,
  error: null,
  executions: [],
  currentExecution: undefined,
  refetch: vi.fn(),
}

vi.mock('../../hooks/useRunWorkshop', () => ({
  useRunWorkshop: () => hookState,
}))

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ user: { id: 'u1', tenant_id: 't1' }, token: 'tok' }),
}))

import WorkshopEditor from './WorkshopEditor'

const APP = {
  id: 'app-1',
  name: 'Demo App',
  graph: {
    nodes: [
      { id: 'n1', type: 'table', position: { x: 0, y: 0 }, data: { label: 'Table 1' } },
      { id: 'n2', type: 'filter', position: { x: 200, y: 0 }, data: { label: 'Filter 1', field: 'status', operator: '==', value: 'active' } },
    ],
    edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
  },
}

function mockFetchApp(once: object = APP) {
  ;(globalThis as any).fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => once,
    text: async () => JSON.stringify(once),
  })
}

function renderEditor() {
  return render(
    <MemoryRouter initialEntries={['/workshop/editor/app-1']}>
      <Routes>
        <Route path="/workshop/editor/:appId" element={<WorkshopEditor />} />
      </Routes>
    </MemoryRouter>
  )
}

beforeEach(() => {
  runMock.mockReset()
  runMock.mockResolvedValue({})
  hookState.isLoading = false
  hookState.error = null
  hookState.executions = []
  hookState.currentExecution = undefined
  mockFetchApp()
})

describe('WorkshopEditor — Run integration', () => {
  it('test_run_button_visible', async () => {
    renderEditor()
    const runButton = await screen.findByRole('button', { name: /Run/ })
    expect(runButton).toBeInTheDocument()
  })

  it('test_run_button_clicked_calls_api', async () => {
    renderEditor()
    const runButton = await screen.findByRole('button', { name: /Run/ })
    fireEvent.click(runButton)
    await waitFor(() => {
      expect(runMock).toHaveBeenCalledTimes(1)
    })
  })

  it('test_execution_panel_shows_status', async () => {
    hookState.currentExecution = {
      id: 'ex-1',
      app_id: 'app-1',
      tenant_id: 't1',
      status: 'completed',
      started_at: '2026-07-25T00:00:00.000Z',
      completed_at: '2026-07-25T00:00:01.000Z',
      duration_ms: 12,
      results: {
        n1: { node_id: 'n1', node_type: 'table', status: 'done', output: { count: 2 }, error: null, duration_ms: 5 },
        n2: { node_id: 'n2', node_type: 'filter', status: 'done', output: { count: 1 }, error: null, duration_ms: 7 },
      },
      error_message: null,
    }
    renderEditor()
    const panel = await screen.findByLabelText('Execution status')
    expect(panel).toHaveTextContent('Table 1')
    expect(panel).toHaveTextContent('Filter 1')
    expect(panel).toHaveTextContent('✓ passed')
  })

  it('test_node_color_updates_on_result', async () => {
    mockFetchApp({
      ...APP,
      graph: {
        ...APP.graph,
        nodes: [
          { id: 'n1', type: 'table', position: { x: 0, y: 0 }, data: { label: 'Table 1', executionStatus: 'done' } },
          { id: 'n2', type: 'filter', position: { x: 200, y: 0 }, data: { label: 'Filter 1', executionStatus: 'error' } },
        ],
      },
    })
    renderEditor()
    await waitFor(() => {
      const statusNodes = document.querySelectorAll('[data-execution-status]')
      expect(statusNodes.length).toBe(2)
    })
    const [successNode, failedNode] = document.querySelectorAll('[data-execution-status]')
    expect(successNode.getAttribute('data-execution-status')).toBe('done')
    expect(failedNode.getAttribute('data-execution-status')).toBe('error')
    expect(successNode.className).toContain('border-emerald-500')
    expect(failedNode.className).toContain('border-rose-500')
  })

  it('test_error_state_on_api_failure', async () => {
    hookState.error = new Error('server exploded')
    renderEditor()
    const errBanner = await screen.findByText('server exploded')
    expect(errBanner).toBeInTheDocument()
  })
})
