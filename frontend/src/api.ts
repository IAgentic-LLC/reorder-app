const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export interface ReorderRequestResponse {
  thread_id: string
  pending_approval: boolean
  answer: string | null
}

export interface ApprovalResponse {
  thread_id: string
  logged: boolean
  note: string
  purchase_order_queued: boolean
}

export interface ProblemDetail {
  type: string
  title: string
  status: number
  detail: string
}

export class ApiError extends Error {
  problem: ProblemDetail

  constructor(problem: ProblemDetail) {
    super(problem.detail)
    this.problem = problem
  }
}

async function postJson<T>(path: string, token: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw new ApiError((await response.json()) as ProblemDetail)
  }
  return (await response.json()) as T
}

export function startReorderRequest(
  token: string,
  question: string,
): Promise<ReorderRequestResponse> {
  return postJson<ReorderRequestResponse>('/v1/reorder-requests', token, { question })
}

export function decideReorderRequest(
  token: string,
  threadId: string,
  approved: boolean,
  note: string,
): Promise<ApprovalResponse> {
  return postJson<ApprovalResponse>(`/v1/reorder-requests/${threadId}/decision`, token, {
    approved,
    note,
  })
}
