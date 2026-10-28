import { useCallback, useEffect, useRef, useState } from 'react'
import { DashboardContext } from './lib/context'
import { assertSnapshot, newestSnapshot, request } from './lib/utils'

export default function LiveProvider({ children }) {
  const [snapshot, setSnapshot] = useState(null)
  const [connection, setConnection] = useState('connecting')
  const [lastSeen, setLastSeen] = useState(null)
  const [token, setToken] = useState('')
  const [role, setRole] = useState('viewer')
  const [notice, setNotice] = useState(null)
  const [diagnostics, setDiagnostics] = useState([])
  const [busy, setBusy] = useState(false)
  const [revision, setRevision] = useState(0)
  const socket = useRef(null)
  const inFlight = useRef(false)

  const report = useCallback((error) => {
    const entry = {
      message: error.message,
      code: error.code || 'client_error',
      request_id: error.requestId || null,
      at: new Date().toISOString(),
    }
    setNotice({ ...entry, type: 'error' })
    setDiagnostics((rows) => [entry, ...rows].slice(0, 20))
  }, [])

  useEffect(() => {
    let closed = false,
      timer,
      attempts = 0,
      lastSnapshotAt = Date.now(),
      receivedLiveSnapshot = false
    const controller = new AbortController()
    request('/network/state', { signal: controller.signal })
      .then((data) => {
        if (!closed && !receivedLiveSnapshot) {
          const next = assertSnapshot(data)
          setSnapshot((previous) => newestSnapshot(previous, next))
        }
      })
      .catch((error) => {
        if (!closed && error.name !== 'AbortError') report(error)
      })
    function connect() {
      if (closed) return
      const ws = new WebSocket(
        `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/v1/ws`,
      )
      socket.current = ws
      lastSnapshotAt = Date.now()
      ws.onmessage = (event) => {
        if (closed || socket.current !== ws) return
        try {
          const message = JSON.parse(event.data)
          if (message.type === 'snapshot') {
            const next = assertSnapshot(message.data)
            receivedLiveSnapshot = true
            lastSnapshotAt = Date.now()
            setSnapshot((previous) => newestSnapshot(previous, next))
            setLastSeen(Date.now())
            setConnection('live')
            attempts = 0
          }
        } catch (error) {
          report(error)
          setConnection('offline')
          ws.close()
        }
      }
      ws.onclose = () => {
        if (closed || socket.current !== ws) return
        socket.current = null
        setConnection('offline')
        timer = setTimeout(connect, Math.min(10000, 1000 * 2 ** attempts++))
      }
      ws.onerror = () => ws.close()
    }
    connect()
    const watchdog = setInterval(() => {
      if (socket.current && Date.now() - lastSnapshotAt >= 10000) {
        setConnection('offline')
        socket.current.close()
      }
    }, 1000)
    return () => {
      closed = true
      clearTimeout(timer)
      clearInterval(watchdog)
      controller.abort()
      socket.current?.close()
    }
  }, [report])

  const refresh = useCallback(async () => {
    setRevision((value) => value + 1)
    try {
      const fresh = await request('/network/state')
      const next = assertSnapshot(fresh)
      setSnapshot((previous) => newestSnapshot(previous, next))
      setLastSeen(Date.now())
    } catch (error) {
      report(error)
    }
  }, [report])
  const read = useCallback((path, options) => request(path, { ...options, token }), [token])
  const mutate = useCallback(
    async (path, body = {}, success = 'Request completed') => {
      if (inFlight.current) return null
      inFlight.current = true
      setBusy(true)
      setNotice(null)
      try {
        const result = await request(path, { method: 'POST', body, token })
        try {
          const fresh = await request('/network/state')
          const next = assertSnapshot(fresh)
          setSnapshot((previous) => newestSnapshot(previous, next))
          setLastSeen(Date.now())
          setNotice({ type: 'success', message: success })
        } catch (error) {
          setConnection('offline')
          report({
            ...error,
            code: 'state_refresh_failed',
            requestId: error.requestId,
            message:
              'The action completed, but its latest state could not be loaded. Inspect the state before retrying.',
          })
        }
        setRevision((value) => value + 1)
        return result
      } catch (error) {
        report(error)
        return null
      } finally {
        inFlight.current = false
        setBusy(false)
      }
    },
    [token, report],
  )
  const login = async (value) => {
    try {
      const session = await request('/auth/session', { token: value })
      setToken(value)
      setRole(session.role)
      setNotice({ type: 'success', message: `Connected with ${session.role} permissions` })
      return true
    } catch (error) {
      report(error)
      return false
    }
  }
  const logout = () => {
    setToken('')
    setRole('viewer')
    setNotice({ type: 'success', message: 'Token removed from this tab' })
  }
  return (
    <DashboardContext.Provider
      value={{
        snapshot,
        connection,
        lastSeen,
        role,
        notice,
        setNotice,
        diagnostics,
        busy,
        revision,
        refresh,
        read,
        mutate,
        login,
        logout,
        report,
        canOperate: connection === 'live' && role !== 'viewer' && !busy,
        canAdmin: connection === 'live' && role === 'admin' && !busy,
      }}
    >
      {children}
    </DashboardContext.Provider>
  )
}
