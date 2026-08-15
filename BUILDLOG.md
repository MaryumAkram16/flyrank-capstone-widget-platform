# Build Log — AI usage, honestly

## Phase 1 — Design
- Used Claude to draft the initial data model and API surface split (owner /
  delivery / submission paths) after I decided the stack (FastAPI + SQLite) and
  scope (signup form + CTA popover) myself.
- Changed: tightened the `submissions` table to denormalize `tenant_id` so every
  dashboard query is a single-column filter instead of a join — this was my call
  after re-reading §6's tenant-isolation requirement.
- Where AI was wrong / needed correction: (none yet in Phase 1)

## Phase 2 — Hardened submission path
- Used Claude to scaffold the FastAPI app: models, routers, services
  (rate_limit, spam, geo, notify), repositories, and the pytest suite.
- Changed / caught: the submission body is parsed manually with
  `request.json()` + `SubmissionCreate.model_validate()` instead of as a
  FastAPI body parameter — I asked for this so malformed JSON and oversized
  field values both return the same clean `{"error": ...}` shape as a 400,
  rather than mixing FastAPI's default 422 shape with a custom 400 shape.
- Where AI was wrong / needed correction: the first draft only guarded
  oversized *field values* via Pydantic, not an oversized *request body*
  (e.g. hundreds of fields). I added the `reject_oversized_bodies` middleware
  in `main.py` (Content-Length check → 413) after re-reading Probe 2 — a
  large-but-individually-valid payload wasn't covered otherwise. Verified via
  `test_oversized_body_rejected_with_413`.
- Every claim below was run for real, not assumed: `pytest -q` (11 passed)
  and a live `uvicorn` + `curl` pass against a seeded widget (see
  `EVIDENCE.md` for the actual transcripts).
