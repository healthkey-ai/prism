import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import App from '../App'

// Stub window.location.reload so the 401 interceptor doesn't throw in jsdom
Object.defineProperty(window, 'location', {
  writable: true,
  value: { ...window.location, reload: vi.fn() },
})

vi.mock('../api/client', () => ({
  fetchCurrentUser:  vi.fn(),
  fetchMetrics:      vi.fn(),
  fetchFormSettings: vi.fn(),
  fetchSavedCohorts: vi.fn(),
  login:             vi.fn(),
  logout:            vi.fn(),
  signup:            vi.fn(),
  createSavedCohort: vi.fn(),
  updateSavedCohort: vi.fn(),
  deleteSavedCohort: vi.fn(),
  default: {},
}))

import * as client from '../api/client'

describe('App — unauthenticated', () => {
  beforeEach(() => {
    vi.mocked(client.fetchCurrentUser).mockRejectedValue({ response: { status: 401 } })
  })

  afterEach(() => vi.clearAllMocks())

  it('renders the login form when not authenticated', async () => {
    render(<App />)
    expect(await screen.findByPlaceholderText('you@example.com')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument()
  })

  it('never calls fetchMetrics while on the login page', async () => {
    render(<App />)
    await screen.findByPlaceholderText('you@example.com')
    // Wait past the useAnalytics debounce (400 ms) to catch any stray calls
    await new Promise(r => setTimeout(r, 500))
    expect(client.fetchMetrics).not.toHaveBeenCalled()
  })

  it('email input retains focus and value after typing', async () => {
    const user = userEvent.setup()
    render(<App />)
    const emailInput = await screen.findByPlaceholderText('you@example.com')

    await user.click(emailInput)
    await user.type(emailInput, 'researcher@hospital.org')

    expect(emailInput).toHaveFocus()
    expect(emailInput).toHaveValue('researcher@hospital.org')
  })

  it('password input retains focus and value after typing', async () => {
    const user = userEvent.setup()
    render(<App />)
    const passwordInput = await screen.findByPlaceholderText('••••••••')

    await user.click(passwordInput)
    await user.type(passwordInput, 'secret123')

    expect(passwordInput).toHaveFocus()
    expect(passwordInput).toHaveValue('secret123')
  })
})
