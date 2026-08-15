# Evidence — one proof per Definition-of-Done checkbox (§6 of the brief)

## Design gate (Phase 1)
- [x] One-page design doc written: see `DESIGN.md` (data model, embed flow, API
      surface for all three request paths, one explicit non-goal).

## Public submission API
- [x] Cross-origin submission works (CORS + preflight)

  ```
  $ curl -s -X POST http://localhost:8000/submissions \
      -H "Origin: http://localhost:5500" -H "Content-Type: application/json" \
      -d '{"widget_id":"<id>","data":{"email":"visitor@example.com"},"website":""}' -i

  HTTP/1.1 201 Created
  access-control-allow-origin: http://localhost:5500
  vary: Origin
  {"id":"67728b1f-...","widget_id":"<id>","data":{"email":"visitor@example.com"},
   "geo_country":null,"geo_city":null,"is_spam":false,"created_at":"2026-08-15T13:44:31Z"}
  ```

  Also covered by `tests/test_submissions.py::test_cors_preflight_allows_configured_origin`
  and `::test_valid_submission_is_stored_and_visible_in_dashboard`.

- [x] Malformed/oversized payload → clean 4xx, never 500

  ```
  $ curl -s -X POST http://localhost:8000/submissions -H "Content-Type: application/json" \
      -d '{"widget_id":"<id>","data":{"email":"xxxx...(3000 chars)"}}' -i
  HTTP/1.1 400 Bad Request
  ```

  Tests: `test_malformed_payload_returns_clean_4xx`,
  `test_oversized_field_value_rejected`, `test_oversized_body_rejected_with_413`.

## Abuse protection
- [x] Rate limiting returns 429 under a burst, service stays up —
      `test_burst_triggers_429_then_service_recovers` (25 rapid submissions to
      the same widget → last one is 429; `/health` still returns 200
      immediately after).
- [x] Honeypot blocks a spam submission —
      `test_honeypot_filled_marks_submission_as_spam`. Live proof:

  ```
  $ curl -s -X POST http://localhost:8000/submissions -H "Content-Type: application/json" \
      -d '{"widget_id":"<id>","data":{"email":"bot@example.com"},"website":"http://spam.example"}' -i
  HTTP/1.1 201 Created   # accepted from the bot's POV, stored with is_spam=true internally
  ```

## Enrichment & safe side effects
- [x] Provider A down → provider B answers —
      `test_provider_a_down_falls_back_to_provider_b`
      (`FORCE_DOWN_A=True`, provider B mocked to answer, result.provider == "B").
- [x] Both down → submission still stored —
      `test_all_providers_down_submission_still_succeeds` (201, `geo_country: null`).
- [x] Failing email/webhook doesn't block the submission —
      `test_failing_email_side_effect_does_not_block_submission`
      (`notify.FORCE_FAIL = True` → still 201, still stored).

## Widget delivery
- [x] Config endpoint returns correct cache headers:
  ```
  $ curl -s http://localhost:8000/widgets/<id>/config -i
  HTTP/1.1 200 OK
  cache-control: public, max-age=60
  access-control-allow-origin: *
  ```
- [x] Widget JS served as a versioned bundle — `/widget/v1.js` (immutable,
      1-year cache; a real release bumps `CURRENT_BUNDLE_VERSION` in
      `app/routers/public.py` to `v2`, which is a new URL, never mutated
      content at the old one). `/widget.js` stays as a short-cached
      (`max-age=300`) alias for unversioned embeds:
  ```
  $ curl -s http://localhost:8000/widget/v1.js -i
  HTTP/1.1 200 OK
  cache-control: public, max-age=31536000, immutable
  content-type: application/javascript
  ```
- [x] Widget renders on a second-origin page — real two-process run: API on
      `:8000`, `test-site/` served via `python -m http.server 5500`. Full
      cross-origin chain proven live (see transcript below) and covered by
      `tests/test_delivery.py::test_full_second_origin_flow_config_then_submit`:
  ```
  1. GET  http://localhost:8000/widget/v1.js                         -> 200
  2. GET  http://localhost:8000/widgets/<id>/config  (Origin :5500)   -> 200,
     access-control-allow-origin: http://localhost:5500
  3. POST http://localhost:8000/submissions          (Origin :5500)   -> 201,
     access-control-allow-origin: http://localhost:5500
  4. GET  http://localhost:8000/api/dashboard/widgets/<id>/stats (X-API-Key) ->
     {"widget_id":"<id>","total":1,"spam_blocked":0,"with_geo":0,
      "last_7_days":{"2026-08-15":1}}
  ```

## Widget management
- [x] Authenticated CRUD; unauthenticated requests rejected — `POST /api/widgets`
      requires `X-API-Key`; missing/invalid key → 401. Covered by
      `test_missing_api_key_is_rejected`, `test_invalid_api_key_is_rejected`.
- [x] Multi-tenant isolation proven — `tests/test_isolation.py`, six tests:
      tenant A can't read, edit, or delete tenant B's widget (all 404, not a
      403 that would leak existence); tenant A's widget list never contains
      tenant B's widgets; tenant A's dashboard stats/submissions calls against
      tenant B's widget id are 404; tenant B still sees their own data intact
      throughout.

## Tests & docs
- [x] Automated tests cover CORS, invalid payload, oversized payload, rate
      limiting, spam control, provider fallback, and tenant isolation:
  ```
  $ pytest -q
  ........................                                               [100%]
  24 passed in 1.00s
  ```
- [x] README architecture diagram + setup instructions present.

## Phase 4 — Demo rehearsal (live transcript)

Ran the full `DEMO.md` script against a real running server. All beats
matched expectations except one flagged limitation:

```
BEAT 1: embed_snippet -> <script src="http://localhost:8000/widget/v1.js?id=..."></script>
BEAT 4a: invalid payload -> 400
BEAT 4b: disallowed origin preflight -> 400, no access-control-allow-origin echoed
BEAT 4c: burst of 22 -> last status 429; /demo/reset clears it before the next beat
BEAT 5: provider A forced down -> submission still 201 (geo_country: null in
        this sandbox -- see the warning note in DEMO.md: outbound calls to
        ip-api.com/ipapi.co are blocked by this sandbox's network policy, so
        only the fallback *logic* was proven here, via the mocked test; real
        geo data needs a one-time check on an unrestricted machine)
BEAT 6: email side effect forced to fail -> submission still 201
BEAT 7: dashboard stats reflect every submission from beats 3-6
```

Added a `/demo/*` control router (geo-provider-a/b toggle, email side-effect
toggle, reset) specifically because Probes 4 and 5 ask an evaluator to
"disable" a live dependency -- without it, that was only possible by editing
Python globals and restarting the server, which isn't demo-safe. Test suite
now at 27/27 (`tests/test_demo_toggles.py` added).

## Stretch — minimal HTML dashboard view

Not required by §6, added as polish. Server-rendered, no frontend build.
Live-generated and inspected (not just unit-tested):

```
$ curl -s "http://localhost:8000/api/dashboard/widgets/<id>/view?key=<key>" -o preview.html
$ curl -s -o /dev/null -w "%{http_code}\n" ".../view?key=<key>"
200
$ grep alert preview.html
<td>&lt;script&gt;alert(1)&lt;/script&gt;</td>
```

Confirms a real stored-XSS attempt via the public submission endpoint renders
escaped, not executable, in the owner's dashboard. Full HTML output visually
reviewed (stats row + submissions table render correctly with real seeded +
submitted data). Covered by `tests/test_dashboard_view.py` (5 tests: key
required, invalid key rejected, stats+table render, XSS escaping, other
tenant's key gets 404, empty state). Suite now 32/32.

## Stretch — real-time SSE dashboard

Not required by §6, listed as a stretch goal in §9 ("new submissions appear
live via WebSockets or Server-Sent Events"). Server-Sent Events chosen over
WebSockets since the feed is one-directional (server -> browser only).

Unit-tested: the pub/sub broker itself (`app/services/events.py`) and the
exact wiring point — `tests/test_live_stream.py` confirms submissions.py
calls `events.publish()` with the right payload for real submissions, and
does NOT call it for spam (a bot's submission shouldn't animate a phantom
row into the live view), and that a broadcast failure never breaks the
submission response (same "never blocks the main path" rule as email/geo).

Real proof — genuinely live, two separate OS processes (not an in-process
test double):
```
$ curl -N -s "http://localhost:8000/api/dashboard/widgets/<id>/stream?key=<key>" > stream_output.txt &
$ curl -s -X POST http://localhost:8000/submissions -H "Content-Type: application/json" \
    -d '{"widget_id":"<id>","data":{"email":"live-proof@example.com"}}'
{"id":"0791fe78-...","widget_id":"<id>","data":{"email":"live-proof@example.com"},...}

$ cat stream_output.txt
event: connected
data: {}

event: submission
data: {"id": "0791fe78-...", "data": {"email": "live-proof@example.com"}, "geo_country": null, "geo_city": null, "created_at": "2026-08-15T14:51:12.261957"}
```
The submission id and data in the stream exactly match the POST response —
confirmed live, not simulated.

Also fetched the actual `/view` HTML and confirmed the embedded `EventSource`
client points at the correct `/stream?key=...` URL with the widget id and
API key correctly JSON-encoded (not string-concatenated — avoids breaking on
a key/id containing a quote character), and that submission data client-side
uses `textContent`, never `innerHTML`, for the same stored-XSS reason as the
server-rendered rows.

**Honest limitation, not hidden**: this couldn't be proven with an in-process
pytest test using `httpx.AsyncClient`/`TestClient` — httpx 0.27.x's
`ASGITransport` fully drains a streaming response internally before
returning control to the caller, which deadlocks against a generator that
only terminates on client disconnect. Confirmed by hand (see BUILDLOG.md for
the debugging trail). This is a test-harness limitation, not an application
bug — real browsers and curl stream incrementally over a real socket and
don't hit it, which is exactly what the two-process proof above demonstrates.

Suite now 41/41.
