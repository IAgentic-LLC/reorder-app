"""Chapter 5: a real API in front of the reorder agent's unchanged logic.

Wraps `reliable_agents_labs.reorder_agent.ask_reorder_agent_with_tools`
(imported, not copied, chapter 4's whole point is that this logic never
gets rewritten) behind a FastAPI endpoint with a typed request/response
contract and one consistent error shape, instead of a bare 500 with a
stack trace a browser has no business seeing.

No authentication yet, deliberately. Chapter 6 adds it. Every request this
endpoint accepts right now is anonymous, on purpose, so the gap stays
visible instead of getting quietly patched over before its own chapter.
"""

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from reliable_agents_labs.models import ModelClient
from reliable_agents_labs.reorder_agent import ask_reorder_agent_with_tools

load_dotenv()

app = FastAPI(title="reorder-app")


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
) -> AnswerResponse:
    try:
        answer = await ask_reorder_agent_with_tools(payload.question, client=client)
    except Exception as exc:
        raise UpstreamModelError(detail=str(exc)) from exc
    return AnswerResponse(answer=answer)
