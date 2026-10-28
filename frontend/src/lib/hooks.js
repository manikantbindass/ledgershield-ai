import { useEffect, useState } from 'react'
import { useDashboard } from './context'

export function useResource(path, live = true) {
  const { read, snapshot, revision, connection } = useDashboard()
  const tick = live ? snapshot?.metrics.simulated_seconds : 0
  const instance = snapshot?.instance_id
  const [result, setResult] = useState({ path: null, data: null, error: null })
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    read(path, { signal: controller.signal })
      .then((data) => setResult({ path, data, error: null }))
      .catch((error) => {
        if (error.name !== 'AbortError')
          setResult((previous) => ({
            path,
            data: previous.path === path ? previous.data : null,
            error,
          }))
      })
    return () => controller.abort()
  }, [path, read, tick, instance, revision, retry, connection])
  return {
    data: result.path === path ? result.data : null,
    error: result.path === path ? result.error : null,
    loading: result.path !== path,
    retry: () => setRetry((value) => value + 1),
  }
}

export function usePaged(path) {
  const [q, setQ] = useState('')
  const [offset, setOffset] = useState(0)
  const limit = 10
  const resource = useResource(`${path}?limit=${limit}&offset=${offset}&q=${encodeURIComponent(q)}`)
  return {
    ...resource,
    q,
    offset,
    limit,
    setOffset,
    search: (value) => {
      setQ(value)
      setOffset(0)
    },
  }
}
