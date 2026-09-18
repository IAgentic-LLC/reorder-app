"""Chapters 5-7: a real API in front of the reorder agent's unchanged
logic, with real identity on every request and, from chapter 7 on, a
real durable workflow instead of a stateless question/answer call.

Wraps `reliable_agents_labs.reorder_agent.ask_reorder_agent_with_tools`
and `reliable_agents_labs.reorder_workflow.build_approval_workflow`
(imported, not copied, chapter 4's whole point is that this logic never
gets rewritten) behind a FastAPI app with a typed request/response
contract and one consistent error shape, instead of a bare 500 with a
stack trace a browser has no business seeing.
"""

import asyncio
import sys
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv

if sys.platform == "win32":
    # Same real, live finding as the test suite's conftest.py: psycopg's
    # async mode refuses to run under Windows' default ProactorEventLoop.
    # This has to run before uvicorn creates its own event loop, so it
    # lives here, at module import time, not inside a function.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.types import Command
from pydantic import BaseModel
from reliable_agents_labs.inventory import check_inventory
from reliable_agents_labs.models import ModelClient
from reliable_agents_labs.reorder_agent import ask_reorder_agent_with_tools

from reorder_app.auth import Principal, register_auth_exception_handlers, verify_token
from reorder_app.jobs import extract_sku, get_queue
from reorder_app.workflow import build_persistent_approval_workflow, get_postgres_checkpointer

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One real Postgres connection pool for the app's whole lifetime,
    # not one per request. `.setup()` creates the checkpointer's own
    # tables if they don't exist yet, safe to call every startup.
    async with get_postgres_checkpointer() as checkpointer:
        await checkpointer.setup()
        app.state.reorder_graph = await build_persistent_approval_workflow(checkpointer)

        # Chapter 9: the same queue a worker process drains, opened once
        # for this app's whole lifetime, not once per request.
        job_queue = get_queue()
        await job_queue.connect()
        app.state.job_queue = job_queue
        try:
            yield
        finally:
            await job_queue.disconnect()


app = FastAPI(title="reorder-app", lifespan=lifespan)
register_auth_exception_handlers(app)

# Chapter 8: the React frontend runs on a different origin (Vite's dev
# server, http://localhost:5173) than this API (http://127.0.0.1:8000).
# Without this, the browser's own same-origin policy blocks every request
# before it reaches a single route, no code here can catch or fix that.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


class AnswerResponse(BaseModel):
    answer: str


class ProblemDetail(BaseModel):
    """RFC 7807 (Problem Details for HTTP APIs), not an invented shape.
    A frontend gets a named, standard contract instead of guessing what
    this API's own error format happens to be this week.
    """

    type: str
    title: str
    status: int
    detail: str


class UpstreamModelError(Exception):
    """Raised when the model call itself fails, a provider outage, a
    malformed tool response, anything below this API's own control.
    Never let that reach a caller as a raw traceback.
    """

    def __init__(self, detail: str) -> None:
        self.detail = detail


@app.exception_handler(UpstreamModelError)
async def handle_upstream_model_error(request: Request, exc: UpstreamModelError) -> JSONResponse:
    problem = ProblemDetail(
        type="https://reorder-app.dev/problems/upstream-model-error",
        title="Upstream model error",
        status=502,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=502,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


async def get_model_client() -> ModelClient | None:
    """The real seam this chapter's tests depend on. Returning `None` here
    means "use the real, config-driven adapter", exactly what
    `ask_reorder_agent_with_tools` already does when its own `client`
    argument is `None`. A test overrides this dependency with a
    `ScriptedModelClient` instead, no real network call, no real cost,
    fully deterministic.
    """
    return None


@app.post("/v1/questions", response_model=AnswerResponse)
async def ask_question(
    payload: QuestionRequest,
    client: ModelClient | None = Depends(get_model_client),
    principal: Principal = Depends(verify_token),
) -> AnswerResponse:
    try:
        answer = await ask_reorder_agent_with_tools(payload.question, client=client)
    except Exception as exc:
        raise UpstreamModelError(detail=str(exc)) from exc
    return AnswerResponse(answer=answer)


class ReorderRequestResponse(BaseModel):
    thread_id: str
    pending_approval: bool
    answer: str | None = None


class ApprovalDecision(BaseModel):
    approved: bool
    note: str = ""


class ApprovalResponse(BaseModel):
    thread_id: str
    logged: bool
    note: str
    purchase_order_queued: bool = False


_EMPTY_APPROVAL_STATE = {
    "question": "",
    "answer": "",
    "reorder": False,
    "approved": False,
    "note": "",
    "logged": False,
}


@app.post("/v1/reorder-requests", response_model=ReorderRequestResponse)
async def start_reorder_request(
    request: Request,
    payload: QuestionRequest,
    principal: Principal = Depends(verify_token),
) -> ReorderRequestResponse:
    """Chapter 7: unlike `/v1/questions`, this run's state doesn't
    disappear when this request finishes. A fresh `thread_id` names it;
    any process holding the same Postgres connection string can resume
    it later, by name, whether that's a different terminal seconds
    later or the same server after a real restart.
    """
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    try:
        result = await request.app.state.reorder_graph.ainvoke(
            {**_EMPTY_APPROVAL_STATE, "question": payload.question}, config
        )
    except Exception as exc:
        raise UpstreamModelError(detail=str(exc)) from exc

    if "__interrupt__" in result:
        return ReorderRequestResponse(thread_id=thread_id, pending_approval=True, answer=None)
    return ReorderRequestResponse(
        thread_id=thread_id, pending_approval=False, answer=result.get("answer")
    )


@app.post("/v1/reorder-requests/{thread_id}/decision", response_model=ApprovalResponse)
async def decide_reorder_request(
    request: Request,
    thread_id: str,
    payload: ApprovalDecision,
    principal: Principal = Depends(verify_token),
) -> ApprovalResponse:
    """Resumes a run paused by `start_reorder_request`, by `thread_id`,
    from whatever process happens to be handling this request, not
    necessarily the same one that started it.
    """
    config = {"configurable": {"thread_id": thread_id}}
    try:
        result = await request.app.state.reorder_graph.ainvoke(
            Command(resume={"approved": payload.approved, "note": payload.note}), config
        )
    except Exception as exc:
        raise UpstreamModelError(detail=str(exc)) from exc

    queued = False
    if result.get("logged"):
        # Chapter 9: an approved, logged reorder is the one branch worth
        # a real purchase order, placed off the request path so a slow
        # or unreliable supplier call never makes this endpoint wait.
        sku = extract_sku(result.get("question", ""))
        if sku is not None:
            record = check_inventory(sku)
            if record is not None:
                job = await request.app.state.job_queue.enqueue(
                    "place_purchase_order",
                    key=f"purchase-order:{thread_id}",
                    thread_id=thread_id,
                    sku=sku,
                    quantity=record.reorder_point * 2,
                )
                queued = job is not None

    return ApprovalResponse(
        thread_id=thread_id,
        logged=result.get("logged", False),
        note=result.get("note", ""),
        purchase_order_queued=queued,
    )
