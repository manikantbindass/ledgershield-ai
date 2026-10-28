import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import LiveProvider from '../src/LiveProvider'
import { useDashboard } from '../src/lib/context'
import { fixture } from './fixtures'

function State() {
  const { connection, snapshot } = useDashboard()
  return (
    <p>
      {connection} / {snapshot?.metrics.simulated_seconds ?? 'none'}
    </p>
  )
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

it('marks a silent socket offline instead of indefinitely showing live data', async () => {
  vi.useFakeTimers()
  let socket
  class SilentSocket {
    constructor() {
      socket = this
    }
    close() {
      this.onclose?.()
    }
  }
  vi.stubGlobal('WebSocket', SilentSocket)
  vi.stubGlobal(
    'fetch',
    vi.fn(() => new Promise(() => {})),
  )
  render(
    <LiveProvider>
      <State />
    </LiveProvider>,
  )
  act(() =>
    socket.onmessage({ data: JSON.stringify({ type: 'snapshot', data: fixture().snapshot }) }),
  )
  expect(screen.getByText('live / 1')).toBeTruthy()
  await act(() => vi.advanceTimersByTimeAsync(10000))
  expect(screen.getByText('offline / 1')).toBeTruthy()
})

it('does not overwrite a newer stream snapshot with the initial HTTP response', async () => {
  let socket, resolve
  class FakeSocket {
    constructor() {
      socket = this
    }
    close() {
      this.onclose?.()
    }
  }
  vi.stubGlobal('WebSocket', FakeSocket)
  vi.stubGlobal(
    'fetch',
    vi.fn(
      () =>
        new Promise((done) => {
          resolve = done
        }),
    ),
  )
  render(
    <LiveProvider>
      <State />
    </LiveProvider>,
  )
  const latest = fixture().snapshot
  latest.metrics.simulated_seconds = 9
  act(() => socket.onmessage({ data: JSON.stringify({ type: 'snapshot', data: latest }) }))
  await act(async () => resolve({ ok: true, json: async () => fixture().snapshot }))
  expect(screen.getByText('live / 9')).toBeTruthy()
})

it('rejects malformed streamed snapshots while retaining the last valid state', () => {
  let socket
  class FakeSocket {
    constructor() {
      socket = this
    }
    close() {
      this.onclose?.()
    }
  }
  vi.stubGlobal('WebSocket', FakeSocket)
  vi.stubGlobal(
    'fetch',
    vi.fn(() => new Promise(() => {})),
  )
  render(
    <LiveProvider>
      <State />
    </LiveProvider>,
  )
  act(() =>
    socket.onmessage({ data: JSON.stringify({ type: 'snapshot', data: fixture().snapshot }) }),
  )
  act(() => socket.onmessage({ data: JSON.stringify({ type: 'snapshot', data: { metrics: {} } }) }))
  expect(screen.getByText('offline / 1')).toBeTruthy()
})

it('distinguishes successful execution from a failed follow-up state refresh', async () => {
  class FakeSocket {
    close() {
      this.onclose?.()
    }
  }
  vi.stubGlobal('WebSocket', FakeSocket)
  let committed = false
  const fetcher = vi.fn(async (url, options) => {
    if (options.method === 'POST') {
      committed = true
      return { ok: true, json: async () => ({ accepted: true }) }
    }
    if (committed) throw new TypeError('offline after action')
    return { ok: true, json: async () => fixture().snapshot }
  })
  vi.stubGlobal('fetch', fetcher)
  function Execute() {
    const { mutate, notice } = useDashboard()
    const [done, setDone] = useState(false)
    return (
      <>
        <button onClick={async () => setDone(!!(await mutate('/simulation/step')))}>Execute</button>
        <p>{done ? 'completed' : 'waiting'}</p>
        <p>{notice?.code}</p>
      </>
    )
  }
  render(
    <LiveProvider>
      <Execute />
    </LiveProvider>,
  )
  fireEvent.click(screen.getByText('Execute'))
  await waitFor(() => expect(screen.getByText('completed')).toBeTruthy())
  expect(screen.getByText('state_refresh_failed')).toBeTruthy()
  expect(fetcher.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1)
})
