import { useCallback, useState } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { ApiError, decideReorderRequest, startReorderRequest } from './api'

type QueueStatus = 'pending' | 'approved' | 'rejected' | 'no_action' | 'error'

interface QueueItem {
  threadId: string
  question: string
  status: QueueStatus
  answer: string | null
  note: string
  errorMessage?: string
}

const STATUS_LABEL: Record<QueueStatus, string> = {
  pending: 'Awaiting approval',
  approved: 'Approved',
  rejected: 'Rejected',
  no_action: 'No reorder needed',
  error: 'Failed',
}

function initialsOf(name: string | undefined): string {
  if (!name) return '?'
  return name.slice(0, 1).toUpperCase()
}

// The agent's own answer text was designed for a terminal (chapters 4-7),
// where "**bold**" reads fine as-is. A browser has no business showing
// raw asterisks, so this renders just enough Markdown to look native.
export function renderAnswer(text: string) {
  const parts = text.split(/\*\*(.+?)\*\*/g)
  return parts.map((part, index) =>
    index % 2 === 1 ? <strong key={index}>{part}</strong> : part,
  )
}

function Header() {
  const { isAuthenticated, isLoading, user, loginWithRedirect, logout } = useAuth0()

  return (
    <header className="header">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true" />
        <div className="brand-text">
          <span className="brand-name">Reorder Desk</span>
          <span className="brand-tag">stock decisions, reviewed by a human</span>
        </div>
      </div>
      <div className="header-actions">
        {isAuthenticated && (
          <div className="user-chip">
            <span className="avatar">{initialsOf(user?.name ?? user?.email)}</span>
            <span>{user?.email}</span>
          </div>
        )}
        {!isLoading && isAuthenticated && (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
          >
            Log out
          </button>
        )}
        {!isLoading && !isAuthenticated && (
          <button type="button" className="btn btn-primary" onClick={() => loginWithRedirect()}>
            Sign in
          </button>
        )}
      </div>
    </header>
  )
}

function RequestForm({ onSubmitted }: { onSubmitted: (item: QueueItem) => void }) {
  const { getAccessTokenSilently } = useAuth0()
  const [question, setQuestion] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault()
      if (!question.trim()) return

      setSubmitting(true)
      setError(null)
      try {
        const token = await getAccessTokenSilently()
        if (!token) throw new Error('No access token available.')
        const result = await startReorderRequest(token, question.trim())
        onSubmitted({
          threadId: result.thread_id,
          question: question.trim(),
          status: result.pending_approval ? 'pending' : 'no_action',
          answer: result.answer,
          note: '',
        })
        setQuestion('')
      } catch (err) {
        setError(err instanceof ApiError ? err.problem.detail : 'The request could not be sent.')
      } finally {
        setSubmitting(false)
      }
    },
    [question, getAccessTokenSilently, onSubmitted],
  )

  return (
    <form className="card request-form" onSubmit={handleSubmit}>
      <label htmlFor="question">Ask the reorder agent</label>
      <div className="request-row">
        <input
          id="question"
          type="text"
          placeholder="Do we need to reorder SKU-3311?"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          disabled={submitting}
        />
        <button type="submit" className="btn btn-primary" disabled={submitting || !question.trim()}>
          {submitting && <span className="spinner" aria-hidden="true" />}
          {submitting ? 'Checking' : 'Check stock'}
        </button>
      </div>
      {error && <p className="form-error">{error}</p>}
    </form>
  )
}

function QueueRow({ item, onUpdate }: { item: QueueItem; onUpdate: (item: QueueItem) => void }) {
  const { getAccessTokenSilently } = useAuth0()
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState<'approve' | 'reject' | null>(null)

  const decide = useCallback(
    async (approved: boolean) => {
      setBusy(approved ? 'approve' : 'reject')
      try {
        const token = await getAccessTokenSilently()
        if (!token) throw new Error('No access token available.')
        const result = await decideReorderRequest(token, item.threadId, approved, note)
        onUpdate({
          ...item,
          status: approved ? 'approved' : 'rejected',
          note: result.note,
        })
      } catch (err) {
        onUpdate({
          ...item,
          status: 'error',
          errorMessage: err instanceof ApiError ? err.problem.detail : 'The decision failed to send.',
        })
      } finally {
        setBusy(null)
      }
    },
    [getAccessTokenSilently, item, note, onUpdate],
  )

  return (
    <div className="card queue-item">
      <div className="queue-item-top">
        <div>
          <div className="queue-question">{item.question}</div>
          <div className="thread-id" title={item.threadId}>
            {item.threadId.slice(0, 8)}
          </div>
        </div>
        <span className={`badge badge-${item.status}`}>{STATUS_LABEL[item.status]}</span>
      </div>

      {item.answer && <p className="queue-answer">{renderAnswer(item.answer)}</p>}
      {item.status === 'error' && <p className="form-error">{item.errorMessage}</p>}

      {item.status === 'pending' && (
        <div className="decision-panel">
          <input
            type="text"
            placeholder="Optional note for the audit trail"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            disabled={busy !== null}
          />
          <button
            type="button"
            className="btn btn-approve"
            onClick={() => decide(true)}
            disabled={busy !== null}
          >
            {busy === 'approve' ? 'Approving' : 'Approve'}
          </button>
          <button
            type="button"
            className="btn btn-reject"
            onClick={() => decide(false)}
            disabled={busy !== null}
          >
            {busy === 'reject' ? 'Rejecting' : 'Reject'}
          </button>
        </div>
      )}

      {(item.status === 'approved' || item.status === 'rejected') && item.note && (
        <p className="decision-note">
          Note: <strong>{item.note}</strong>
        </p>
      )}
    </div>
  )
}

function Dashboard() {
  const [queue, setQueue] = useState<QueueItem[]>([])

  const addItem = useCallback((item: QueueItem) => {
    setQueue((current) => [item, ...current])
  }, [])

  const updateItem = useCallback((updated: QueueItem) => {
    setQueue((current) =>
      current.map((entry) => (entry.threadId === updated.threadId ? updated : entry)),
    )
  }, [])

  return (
    <main className="main">
      <div className="page-heading">
        <h1>Reorder queue</h1>
        <p>Every check runs the same agent Chapter 4 through 7 already built. Nothing here is a mock.</p>
      </div>

      <RequestForm onSubmitted={addItem} />

      <div className="queue-heading">
        <h2>This session</h2>
        <span className="queue-count">
          {queue.length} {queue.length === 1 ? 'request' : 'requests'}
        </span>
      </div>

      {queue.length === 0 ? (
        <div className="queue-empty">Ask about a SKU above to start a real, durable run.</div>
      ) : (
        <div className="queue">
          {queue.map((item) => (
            <QueueRow key={item.threadId} item={item} onUpdate={updateItem} />
          ))}
        </div>
      )}
    </main>
  )
}

function SignedOutGate() {
  const { loginWithRedirect } = useAuth0()
  return (
    <main className="main">
      <div className="gate">
        <div className="brand-mark" aria-hidden="true" style={{ width: 44, height: 44 }} />
        <h1 className="gate-title">Sign in to review reorder requests</h1>
        <p className="gate-subtitle">
          Every request here reaches a real, authenticated API backed by a durable workflow, not a
          demo stub.
        </p>
        <button type="button" className="btn btn-primary" onClick={() => loginWithRedirect()}>
          Sign in
        </button>
      </div>
    </main>
  )
}

function App() {
  const { isAuthenticated, isLoading } = useAuth0()

  return (
    <div className="shell">
      <Header />
      {isLoading ? null : isAuthenticated ? <Dashboard /> : <SignedOutGate />}
    </div>
  )
}

export default App
