import { describe, expect, it } from 'vitest'
import { csvCell, matchedExperiments, newestSnapshot, routeFromHash, toCSV } from '../src/lib/utils'

describe('research data exports and routing', () => {
  it('keeps newer revisions and newer service instances when transports arrive out of order', () => {
    const current = { instance_id: 'new', instance_started_at_ns: '200', revision: 9 }
    expect(newestSnapshot(current, { ...current, revision: 8 })).toBe(current)
    expect(
      newestSnapshot(current, { instance_id: 'old', instance_started_at_ns: '100', revision: 20 }),
    ).toBe(current)
    const reset = { instance_id: 'reset', instance_started_at_ns: '300', revision: 0 }
    expect(newestSnapshot(current, reset)).toBe(reset)
  })
  it('escapes CSV quotes, line breaks and formula injection', () => {
    expect(csvCell('=SUM(A1)')).toBe('"\'=SUM(A1)"')
    expect(csvCell('a,"b"')).toBe('"a,""b"""')
    expect(toCSV([{ id: 'run', reward: -3 }])).toContain('"\'-3"')
  })
  it('rejects unmatched comparisons', () => {
    const base = { seed: 20000, horizon: 10, episodes: 4, environment_config: { validators: 4 } }
    expect(matchedExperiments([base, { ...base }])).toBe(true)
    expect(matchedExperiments([base, { ...base, seed: 10000 }])).toBe(false)
    expect(matchedExperiments([base, { ...base, environment_config: { validators: 7 } }])).toBe(
      false,
    )
    expect(matchedExperiments([base])).toBe(false)
  })
  it('handles deep links and legacy bookmarks', () => {
    expect(routeFromHash('#/reports')).toBe('reports')
    expect(routeFromHash('#alerts')).toBe('security')
    expect(routeFromHash('')).toBe('overview')
  })
})
