import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../src/App'
import { fixture, server } from './fixtures'

let data, fetchMock
class TestSocket {
  static instances = []
  static deliver = true
  constructor() {
    TestSocket.instances.push(this)
    if (TestSocket.deliver)
      queueMicrotask(() =>
        this.onmessage?.({ data: JSON.stringify({ type: 'snapshot', data: data.snapshot }) }),
      )
  }
  close() {
    this.onclose?.()
  }
}

beforeEach(() => {
  data = fixture()
  TestSocket.instances = []
  TestSocket.deliver = true
  window.history.replaceState(null, '', '/#/overview')
  fetchMock = vi.fn(server(data))
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('WebSocket', TestSocket)
})

async function navigate(name) {
  await userEvent.click(screen.getByRole('link', { name, exact: true }))
  await screen.findByRole('heading', { name, level: 1 })
}
async function authenticate() {
  await navigate('Settings & Audit')
  await userEvent.type(
    await screen.findByLabelText('Operator or admin token'),
    'admin-test-' + 'x'.repeat(35),
  )
  await userEvent.click(screen.getByRole('button', { name: 'Verify token' }))
  await screen.findByText('Connected with admin permissions')
}

describe('research dashboard workflows', () => {
  it.each([
    'Overview',
    'Network Explorer',
    'Blockchain Explorer',
    'Security Center',
    'Trust Management',
    'Self-Healing Center',
    'RL Lab',
    'Simulation Lab',
    'Experiment Reports',
    'Settings & Audit',
  ])('navigates to %s with actual resource loading', async (name) => {
    render(<App />)
    await screen.findByText('Consensus is progressing.')
    await navigate(name)
    expect(screen.getByRole('link', { name, exact: true }).getAttribute('aria-current')).toBe(
      'page',
    )
    await waitFor(() => expect(screen.queryByText('Loading measured data…')).toBeNull())
  })

  it('keeps mutations locked for viewers, verifies role and clears credentials', async () => {
    render(<App />)
    await screen.findByText('Consensus is progressing.')
    expect(screen.getByRole('button', { name: '+ Signed transfer' }).disabled).toBe(true)
    await authenticate()
    await navigate('Simulation Lab')
    expect(screen.getByRole('button', { name: 'Start simulation', exact: true }).disabled).toBe(
      false,
    )
    await navigate('Settings & Audit')
    await userEvent.click(screen.getByRole('button', { name: 'Clear access' }))
    await screen.findByText('Token removed from this tab')
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('filters nodes and selects keyboard-operable topology details', async () => {
    render(<App />)
    await screen.findByText('Consensus is progressing.')
    await navigate('Network Explorer')
    await userEvent.type(screen.getByLabelText('Search participants'), 'node_1')
    expect(screen.queryByRole('button', { name: 'node_2', exact: true })).toBeNull()
    const graph = screen.getByRole('button', { name: /Inspect node_1/ })
    fireEvent.keyDown(graph, { key: 'Enter' })
    expect(screen.getByRole('heading', { name: 'Participant / node_1' })).toBeTruthy()
  })

  it('paginates blocks and requests verified block details', async () => {
    render(<App />)
    await screen.findByText('Consensus is progressing.')
    await navigate('Blockchain Explorer')
    await screen.findByRole('button', { name: '#1', exact: true })
    await userEvent.click(screen.getByRole('button', { name: 'Next', exact: true }))
    await screen.findByRole('button', { name: '#10', exact: true })
    await userEvent.click(screen.getByRole('button', { name: 'Previous', exact: true }))
    await userEvent.click(await screen.findByRole('button', { name: '#1', exact: true }))
    await screen.findByText('Hash & linkage verified')
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/v1/blocks/1')).toBe(true)
    await userEvent.click(screen.getByRole('button', { name: 'Transactions', exact: true }))
    await screen.findByText('1 units')
  })

  it('searches the full alert collection and exposes evidence', async () => {
    render(<App />)
    await screen.findByText('Consensus is progressing.')
    await navigate('Security Center')
    await userEvent.type(screen.getByLabelText('Filter security alerts'), 'high')
    await userEvent.click(await screen.findByRole('button', { name: 'Protocol vote violation' }))
    expect(screen.getByText('Raw features and supporting evidence')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Statistical anomaly indicator' })).toBeNull()
  })

  it('records an approved healing outcome and submits bounded scenarios', async () => {
    render(<App />)
    await screen.findByText('Consensus is progressing.')
    await authenticate()
    await navigate('Self-Healing Center')
    await userEvent.click(await screen.findByRole('button', { name: 'quarantine', exact: true }))
    await userEvent.click(
      await screen.findByRole('button', { name: 'Approve local simulator action' }),
    )
    await screen.findByText('Approval processed; inspect the recorded outcome')
    expect(data.actions[0].status).toBe('recovered')
    await navigate('Simulation Lab')
    await userEvent.selectOptions(screen.getByLabelText('Scenario', { exact: true }), 'delay')
    await userEvent.click(screen.getByRole('button', { name: 'Start bounded scenario' }))
    await screen.findByRole('button', { name: 'Stop scenario and restore settings' })
    expect(data.snapshot.active_scenario.latency_ms).toBe(300)
    await userEvent.click(
      screen.getByRole('button', { name: 'Stop scenario and restore settings' }),
    )
    await screen.findByText('Scenario stopped; fault settings restored')
  })

  it('loads recorded losses and runs matched report comparisons', async () => {
    render(<App />)
    await screen.findByText('Consensus is progressing.')
    await authenticate()
    await navigate('RL Lab')
    await userEvent.selectOptions(await screen.findByLabelText('Series'), 'loss')
    expect(screen.getByRole('img', { name: /Mean TD loss/ })).toBeTruthy()
    await navigate('Experiment Reports')
    await userEvent.click(screen.getByRole('button', { name: 'Run matched comparison' }))
    await screen.findByText('Matched policy evaluation completed; results recorded')
    expect(screen.getByRole('button', { name: 'Export episode CSV' }).disabled).toBe(false)
    expect(data.experiments).toHaveLength(3)
  })

  it('supports light theme and mobile navigation without changing access', async () => {
    render(<App />)
    await screen.findByText('Consensus is progressing.')
    await userEvent.click(screen.getByRole('button', { name: 'Switch to light theme' }))
    expect(document.documentElement.dataset.theme).toBe('light')
    await userEvent.click(screen.getByRole('button', { name: 'Open navigation' }))
    expect(
      screen.getByRole('button', { name: 'Close navigation' }).getAttribute('aria-expanded'),
    ).toBe('true')
  })

  it('keeps the last snapshot labeled stale and locks controls after disconnection', async () => {
    render(<App />)
    await screen.findByText('Consensus is progressing.')
    await authenticate()
    act(() => TestSocket.instances.at(-1).onclose())
    await screen.findByText('Live connection lost. Reconnecting automatically.')
    await navigate('Simulation Lab')
    expect(screen.getByRole('button', { name: 'Start bounded scenario' }).disabled).toBe(true)
    expect(screen.getByText(/Showing the last received simulator snapshot/)).toBeTruthy()
  })

  it('shows an honest empty offline startup instead of fake measurements', async () => {
    TestSocket.deliver = false
    fetchMock.mockRejectedValue(new TypeError('offline'))
    render(<App />)
    act(() => TestSocket.instances.at(-1).onclose())
    await screen.findByText('No simulator data available')
    expect(screen.queryByText('Transaction throughput')).toBeNull()
  })
})
