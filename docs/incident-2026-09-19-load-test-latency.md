# Incident Report: Elevated Latency Under Concurrent Load

**Date**: 2026-09-19 · **Severity**: Low (self-triggered, no real customer impact) · **Status**: Resolved, root cause understood, no fix deployed yet

Chapter 33 of *Production AI Products*. This is a real incident, not a hypothetical written for the chapter: chapter 32's own synthetic load agent surfaced it directly, and this report follows the same structure a real production incident review would.

## Timeline

- **02:04 UTC** — `scripts/synthetic_load_agent.py` fired 15 real, concurrently-generated questions at `reorder-app-book3`.
- **02:04–02:05 UTC** — All 15 requests eventually returned `200`. Wall-clock latency per request ranged from 15.86s to 21.94s (p50 17.77s), far above this environment's typical single-request latency (1–3s, observed informally throughout this book).
- **02:05 UTC** — `fly status` checked immediately afterward: exactly two `app` machines, both `started`, no additional machine provisioned during the test.

## Impact

Self-inflicted, by this book's own load test, not a real customer-facing event. No requests failed (15/15 succeeded). The real impact is what this latency would mean for an actual concurrent burst of real traffic: a real user submitting a reorder question during a real busy period would wait fifteen to twenty seconds for an answer, a genuinely poor real experience, not a theoretical one.

## Blast radius

Scoped to `reorder-app-book3` only. `pkgintel-app` and `triage-app` run on entirely separate infrastructure (their own local Docker services, no shared Fly deployment), so this incident could not have affected either of them. Within `reorder-app-book3` itself, both real `app` machines were affected roughly equally; Fly's own load balancer distributed the 15 concurrent requests across both, and neither machine's own health check ever failed during the test.

## Root cause

`reorder-app-book3` runs a **fixed two-machine configuration** (chapter 10's own deploy setup, `shared-cpu-1x`/512MB per `app` machine), with no dynamic auto-scaling configured. Fifteen real, concurrent requests, each requiring a real Gemini API call plus a real Postgres checkpointer write, meant roughly seven to eight requests genuinely competing for each machine's own limited CPU and connection-pool capacity at once. The latency is not a bug in this book's own application code; it is the real, correctly-functioning consequence of running fixed, small infrastructure against a real concurrent load it was never sized for.

## Remediation, and what's deliberately not done here

No infrastructure change has been deployed in response to this incident. Scaling `reorder-app-book3` to more machines, or larger ones, is a real cost decision, not a code fix, and making it inside this chapter would commit this book's own live environment to a higher ongoing bill without the account owner's own explicit choice, the same category of decision chapters 22 and 30 have already deliberately left to a human rather than an autonomous session. What this report does instead: names the real cause precisely, records the real numbers, and hands the actual scaling decision, if the account owner wants to make one, a documented, evidence-based starting point instead of a guess.

## Follow-ups

- If real production traffic for this product ever needs to handle bursts like this one, chapter 34's own graceful-degradation work (queuing, backpressure, or a faster failure mode under saturation) is the more appropriate next step than simply adding machines, since more machines only pushes the same real problem to a higher concurrency threshold, it doesn't remove it.
- This report itself, `docs/incident-2026-09-19-load-test-latency.md`, is the template for any future real incident this book's own live environment produces; the next one should follow the same structure, not invent a new one.
