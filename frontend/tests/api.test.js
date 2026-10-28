import { afterEach, describe, expect, it, vi } from 'vitest'
import { request } from '../src/lib/utils'

afterEach(() => vi.unstubAllGlobals())

describe('API error boundaries', () => {
  it('preserves sanitized error code and request ID', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        json: async () => ({
          error: { code: 'rate_limit_exceeded', detail: 'Try later', request_id: 'request-42' },
        }),
      })),
    )
    await expect(request('/policies/evaluate')).rejects.toMatchObject({
      code: 'rate_limit_exceeded',
      requestId: 'request-42',
      message: 'Try later',
    })
  })
  it('rejects malformed responses and propagates cancellation', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        headers: { get: () => 'request-43' },
        json: async () => {
          throw new SyntaxError('bad JSON')
        },
      })),
    )
    await expect(request('/nodes')).rejects.toMatchObject({
      code: 'invalid_response',
      requestId: 'request-43',
    })
    const cancellation = new DOMException('Cancelled', 'AbortError')
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw cancellation
      }),
    )
    await expect(request('/nodes')).rejects.toBe(cancellation)
  })
})
