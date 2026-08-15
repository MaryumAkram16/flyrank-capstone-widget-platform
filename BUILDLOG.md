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

## Stretch — real-time SSE dashboard
- Used Claude to build an in-process pub/sub broker (`app/services/events.py`),
  wire a `publish()` call into the submission path (non-spam only), add an
  SSE endpoint (`/api/dashboard/widgets/{id}/stream`), and extend the
  dashboard HTML with a vanilla-JS `EventSource` client — no frontend
  framework, consistent with the rest of the capstone.
- Where AI was wrong / needed real correction, twice in a row on the same
  issue: the first two attempts at testing this in-process both hung
  indefinitely. First with `TestClient`'s sync `.stream()` (deadlocks because
  it fully drains the response before returning). Second with
  `httpx.AsyncClient` + `ASGITransport` directly, on the theory that going
  fully async would fix it — it did not; the same httpx version's
  `ASGITransport` has the same full-drain behavior regardless of sync vs.
  async client. Confirmed with a minimal standalone reproduction script
  outside pytest before concluding it was a real library limitation and not
  a bug in the app or the test. Pivoted the test suite to unit-test the
  broker and the exact wiring point (does submissions.py call publish() with
  the right payload, and does it skip spam) via monkeypatching, and did the
  actual "open a stream, post a submission, watch it arrive live" proof
  against a real running server using two real `curl` processes instead —
  which is a stronger proof than an in-process mock would have been anyway.
- `pytest -q` -> 41 passed (32 from the dashboard-table stretch + 9 new:
  4 broker unit tests, 2 auth/ownership checks, 3 wiring tests).

## Stretch — bot defense (proof-of-work) with measured spam reduction
- Used Claude to build the full feature: `app/services/pow.py` (challenge
  issue/verify), a new `GET /widgets/{id}/challenge` endpoint, required
  `challenge_id`/`solution` fields on every submission, and a client-side
  solver in the widget bundle using Web Crypto's `crypto.subtle.digest`.
- This was the most invasive stretch goal — making the challenge fields
  *required* (not optional/best-effort) meant every one of the 41 existing
  tests that posted to `/submissions` needed updating, not just new tests
  added. Went through each test file and either had it solve a real
  challenge (via a new `solve_pow_challenge()` helper that runs the same
  brute-force algorithm as the browser JS, in Python) or, for the
  rate-limit burst test specifically, used a structurally-valid-but-wrong
  challenge since rate limiting runs before challenge verification in the
  pipeline and doesn't need 25 real solves to prove the point.
- Specifically asked for the §9 line to be taken literally — "measure the
  spam reduction" wants a number, not just the mechanism — so built
  `scripts/measure_bot_defense.py` and ran it against a real live server
  rather than describing the mechanism and calling it done.
- Where AI was wrong / needed correction: the first version of the
  measurement script ran all three profiles (naive bot, scripted attacker,
  legitimate visitor) back-to-back against the same widget without
  resetting rate limits between them — 60 total requests against a
  20/minute limit would have had the rate limiter itself block most of the
  later profiles, producing a misleading "100% blocked" number that wasn't
  actually about bot defense. Caught before running it for real by
  reasoning through the numbers first; fixed by calling the existing
  `/demo/reset` endpoint (which already clears rate limits, from the Phase 4
  toggle router) between each profile so the measurement isolates the
  proof-of-work layer specifically.
- Real numbers, not estimated: naive bot 0/20 (100% blocked), scripted
  attacker 0/20 (100% blocked), legitimate visitor 20/20 (0% false
  positives, ~117ms average solve cost). See EVIDENCE.md for the full
  transcript.
- `pytest -q` -> 47 passed (41 from the SSE stretch + 6 new: 2 challenge
  endpoint tests, 4 bot-defense tests — the rest of the increase is from
  extending existing tests, not just adding new ones).
