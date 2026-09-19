# reorder-app

Full-stack product: the reorder agent, hardened. Continues Book 2's Projects 1 and 4.

Companion product code for *Production AI Products* (Book 3 of the "Production AI Agent Engineering" series). Every chapter has a matching git tag here, real, tested, runnable code, not illustrative snippets.

**Status: all 36 chapters complete**, book-wide (this product's own tags: `ch05-end` through `ch35-end`; chapter 4 introduces no new code here, see the manuscript). A real FastAPI backend, Auth0 authentication, a Postgres-backed durable LangGraph workflow, a React frontend, a SAQ background worker, and a live Fly.io deployment (`reorder-app-book3.fly.dev`), plus shared Langfuse tracing (ch16), secret rotation (ch26), a tiered CI/CD pipeline (ch31), a real load test and incident report (ch32-33), and real per-request cost tracking (ch35). 36 tests passing across all five tiers where applicable. Verified live, end to end, in a real browser, as of the book's own closing chapter.

## Repository shape

```
backend/src/reorder_app/   application code
frontend/                    React frontend
workers/                     SAQ background workers
tests/{unit,orchestration,integration,contract,evals}/
config/
docs/diagrams/
scripts/
```

## Testing

Five tiers, same taxonomy as Book 2's `reliable-agents-labs`: `tests/unit`, `tests/orchestration` (scripted fake model), `tests/integration` (real local services), `tests/contract` (real model call), `tests/evals` (golden dataset). Fast tiers run on every push; live tiers run on version tags and manual dispatch only, see `.github/workflows/ci.yml`.
