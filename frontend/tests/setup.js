import { afterEach } from 'vitest'
import { cleanup, configure } from '@testing-library/react'

configure({ asyncUtilTimeout: 5000 })
afterEach(() => {
  cleanup()
  localStorage.clear()
})
