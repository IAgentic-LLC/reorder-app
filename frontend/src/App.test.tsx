import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App, { renderAnswer } from './App'
import * as api from './api'

vi.mock('@auth0/auth0-react', () => ({
  useAuth0: () => ({
    isAuthenticated: true,
    isLoading: false,
    user: { email: 'demo@reorder-app.dev' },
    loginWithRedirect: vi.fn(),
    logout: vi.fn(),
    getAccessTokenSilently: vi.fn().mockResolvedValue('fake-token'),
  }),
}))

describe('renderAnswer', () => {
  it('turns **bold** markers into strong elements instead of leaking asterisks', () => {
    render(<div>{renderAnswer('Currently there are **150 units** in stock.')}</div>)
    const strong = screen.getByText('150 units')
    expect(strong.tagName).toBe('STRONG')
    expect(screen.queryByText(/\*\*/)).toBeNull()
  })
})

describe('Dashboard', () => {
  it('shows approve/reject controls for a pending request, then moves it to approved', async () => {
    vi.spyOn(api, 'startReorderRequest').mockResolvedValue({
      thread_id: 'thread-a',
      pending_approval: true,
      answer: null,
    })
    vi.spyOn(api, 'decideReorderRequest').mockResolvedValue({
      thread_id: 'thread-a',
      logged: true,
      note: 'looks good',
    })

    const user = userEvent.setup()
    render(<App />)

    await user.type(
      screen.getByRole('textbox', { name: /ask the reorder agent/i }),
      'Do we need to reorder SKU-3311?',
    )
    await user.click(screen.getByRole('button', { name: /check stock/i }))

    expect(await screen.findByText(/awaiting approval/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^approve$/i }))

    await waitFor(() => expect(screen.getByText(/^approved$/i)).toBeInTheDocument())
    expect(api.decideReorderRequest).toHaveBeenCalledWith('fake-token', 'thread-a', true, '')
  })

  it('renders a no-reorder-needed result without approval controls', async () => {
    vi.spyOn(api, 'startReorderRequest').mockResolvedValue({
      thread_id: 'thread-b',
      pending_approval: false,
      answer: 'Currently there are **150 units** in stock.',
    })

    const user = userEvent.setup()
    render(<App />)

    await user.type(
      screen.getByRole('textbox', { name: /ask the reorder agent/i }),
      'Do we need to reorder SKU-2040?',
    )
    await user.click(screen.getByRole('button', { name: /check stock/i }))

    expect(await screen.findByText(/no reorder needed/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^approve$/i })).toBeNull()
  })
})
