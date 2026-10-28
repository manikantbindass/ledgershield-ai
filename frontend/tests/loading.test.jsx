import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { Resource } from '../src/components'

it('renders a labeled loading state without fabricated resource content', () => {
  render(
    <Resource resource={{ loading: true, data: null, error: null }}>
      {() => <p>Not ready</p>}
    </Resource>,
  )
  expect(screen.getByRole('status').textContent).toContain('Loading measured data')
  expect(screen.queryByText('Not ready')).toBeNull()
})
