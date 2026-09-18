"""Chapter 6: verifying who's actually asking, not just what they're asking.

JWT verification against a real Auth0 tenant's JWKS endpoint, using PyJWT.
FastAPI's own docs now recommend PyJWT over python-jose for exactly this,
confirmed against a live source while writing this chapter, not assumed
from memory.

There is no session, no cookie, no password stored anywhere in this repo.
The identity of every caller is exactly what its bearer token proves,
nothing this API manages itself, that's the whole point of using an
external identity provider instead of rolling one.
"""

import os

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


# Read lazily, not as module-level constants. A real run of this app
# found the bug a constant would hide: `import reorder_app.auth` (this
# module) happens before `api.py`'s own `load_dotenv()` line runs, so
# reading `os.environ` at import time here saw an empty environment,
# even though `.env` genuinely existed on disk. Reading it inside the
# functions that need it means it doesn't matter what already called
# `load_dotenv()` by the time a real request arrives, only that
# something did before then, which `api.py` still guarantees.
def _auth0_domain() -> str:
    return os.environ.get("AUTH0_DOMAIN", "")


def _auth0_audience() -> str:
    return os.environ.get("AUTH0_AUDIENCE", "")


_bearer_scheme = HTTPBearer()
_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    """Lazy, module-level singleton. PyJWKClient caches the fetched keys
    itself, constructing it once per process avoids re-fetching Auth0's
    JWKS on every single request.
    """
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(f"https://{_auth0_domain()}/.well-known/jwks.json")
    return _jwks_client


class Principal(BaseModel):
    """What a verified token actually proves: a subject identifier, no
    more. Chapter 4's clerk and colleague finally have something a
    request can carry: `sub` is Auth0's opaque, stable identifier for
    whichever client (or, once chapter 8's frontend exists, whichever
    logged-in user) the token was issued to.
    """

    subject: str


class UnauthorizedError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> Principal:
    """The real seam: swap `_get_jwks_client` (module-level) or override
    this whole dependency in a test for a deterministic double instead of
    calling a live Auth0 tenant on every test run, same pattern chapter
    5's `get_model_client` already established.
    """
    token = credentials.credentials
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=_auth0_audience(),
            issuer=f"https://{_auth0_domain()}/",
            # A real, live token against a real tenant failed here first,
            # not a hypothetical: PyJWT's default zero-tolerance `iat`
            # check tripped on a few seconds of ordinary clock skew
            # between this machine and Auth0's own server. 30 seconds of
            # leeway is the standard tolerance for exactly this.
            leeway=30,
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError(detail=str(exc)) from exc
    return Principal(subject=payload["sub"])


def register_auth_exception_handlers(app) -> None:
    @app.exception_handler(UnauthorizedError)
    async def handle_unauthorized(request: Request, exc: UnauthorizedError) -> JSONResponse:
        from reorder_app.api import ProblemDetail

        problem = ProblemDetail(
            type="https://reorder-app.dev/problems/unauthorized",
            title="Unauthorized",
            status=401,
            detail=exc.detail,
        )
        return JSONResponse(
            status_code=401,
            content=problem.model_dump(),
            media_type="application/problem+json",
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        # HTTPBearer itself raises a plain HTTPException (missing header
        # entirely), route that through the same RFC 7807 shape too,
        # rather than let FastAPI's own default {"detail": ...} leak out
        # as a second, inconsistent error format.
        from reorder_app.api import ProblemDetail

        problem = ProblemDetail(
            type="https://reorder-app.dev/problems/unauthorized",
            title="Unauthorized",
            status=exc.status_code,
            detail=str(exc.detail),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )
