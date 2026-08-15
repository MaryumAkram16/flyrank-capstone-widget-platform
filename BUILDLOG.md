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

## Phase 3 — Delivery, dashboard & proof
- Used Claude to add versioned bundle delivery (`/widget/{version}.js`,
  immutable cache, vs. a short-cached `/widget.js` alias), the computed
  `embed_snippet` field on widget creation, and the multi-tenant isolation
  test suite (`tests/test_isolation.py`).
- Changed / caught: I asked specifically for a *real* two-origin proof, not
  just unit tests — Claude ran the actual API on :8000 and the test-site on
  :5500 as two separate processes and curl'd the whole chain (bundle → config
  → submission → dashboard stats), which is what's pasted in `EVIDENCE.md`.
  Unit tests alone (`test_full_second_origin_flow_config_then_submit`) mock
  the origin header rather than running two real servers, so I wanted the
  live version too before calling this checkbox done.
- Where AI was wrong / needed correction: none this phase — the isolation
  tests passed on the first run against the existing `get_for_tenant` /
  `get_public` split from Phase 2, which was designed with this in mind.
- `pytest -q` → 24 passed (11 from Phase 2 + 13 new: 7 isolation, 6 delivery).

## Phase 4 — Demo prep
- Used Claude to write `DEMO.md` (the 7-beat script from §13, timed) and add
  a `/demo/*` toggle router so Probes 4/5's "disable this dependency live"
  can happen against a running server instead of requiring a restart.
- Where AI was wrong / needed correction: the first rehearsal exposed a real
  ordering bug I hadn't caught — beat 4's rate-limit burst test exhausted the
  widget's rate-limit bucket, so beats 5 and 6 right after it both returned
  false 429s instead of demonstrating what they were supposed to. Fixed by
  making `/demo/reset` also clear rate-limit counters, and by calling it
  between beats in the script. Re-ran the full rehearsal after the fix to
  confirm beats 5 and 6 actually show what they claim.
- One honest gap, not hidden: the live rehearsal's geo fallback beat shows
  `geo_country: null` because this build environment's network policy blocks
  ip-api.com/ipapi.co outbound — the fallback *logic* is proven (mocked unit
  test), but real geo data from beat 5 needs a one-time check on a machine
  with normal internet access before the actual demo. Noted in `DEMO.md` and
  `EVIDENCE.md` rather than claimed as verified.
- `pytest -q` → 27 passed (24 from Phase 3 + 3 new demo-toggle tests).

## Stretch — minimal HTML dashboard view
- Used Claude to add a server-rendered `/api/dashboard/widgets/{id}/view`
  route — plain HTML/CSS in an f-string, no frontend build, per §7's own
  guidance ("the grade lives in the backend, not the CSS").
- Specifically asked for HTML-escaping on all submission data before it
  renders, since a visitor's form input is untrusted and this is the one
  surface where it gets turned into HTML — added a test that actually
  submits a `<script>alert(1)</script>` payload through the real public
  endpoint and confirms it renders as escaped text, not executable markup.
- Where AI was wrong / needed correction: none — this one was scoped
  correctly on the first pass.
- `pytest -q` -> 32 passed (27 from Phase 4 + 5 new).
