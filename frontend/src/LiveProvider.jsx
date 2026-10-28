import { useCallback, useEffect, useRef, useState } from 'react'
import { DashboardContext } from './lib/context'
import { request } from './lib/utils'

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
      attempts = 0
    const controller = new AbortController()
    request('/network/state', { signal: controller.signal })
      .then((data) => {
        if (!closed) setSnapshot(data)
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
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          if (message.type === 'snapshot') {
            setSnapshot(message.data)
            setLastSeen(Date.now())
            setConnection('live')
            attempts = 0
          }
        } catch {
          report(new Error('An unreadable live update was ignored.'))
        }
      }
      ws.onclose = () => {
        if (closed) return
        setConnection('offline')
        timer = setTimeout(connect, Math.min(10000, 1000 * 2 ** attempts++))
      }
      ws.onerror = () => ws.close()
    }
    connect()
    return () => {
      closed = true
      clearTimeout(timer)
      controller.abort()
      socket.current?.close()
    }
  }, [report])

  const refresh = useCallback(async () => {
    setRevision((value) => value + 1)
    try {
      const fresh = await request('/network/state')
      setSnapshot(fresh)
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
        const fresh = await request('/network/state')
        setSnapshot(fresh)
        setLastSeen(Date.now())
        setNotice({ type: 'success', message: success })
        refresh()
        return result
      } catch (error) {
        report(error)
        return null
      } finally {
        inFlight.current = false
        setBusy(false)
      }
    },
    [token, refresh, report],
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
