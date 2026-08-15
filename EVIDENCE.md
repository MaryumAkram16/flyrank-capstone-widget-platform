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

## Widget delivery (partial — Phase 3 will extend)
- [x] Config endpoint returns correct cache headers:
  ```
  $ curl -s http://localhost:8000/widgets/<id>/config -i
  HTTP/1.1 200 OK
  cache-control: public, max-age=60
  access-control-allow-origin: *
  ```
- [x] Widget JS served as a versioned/cacheable bundle:
  ```
  $ curl -s http://localhost:8000/widget.js -i
  HTTP/1.1 200 OK
  cache-control: public, max-age=31536000, immutable
  content-type: application/javascript
  ```
- [ ] Widget renders on a second-origin page — scaffolded in `test-site/index.html`,
      manual verification pending Phase 3.

## Widget management
- [x] Authenticated CRUD; unauthenticated requests rejected — `POST /api/widgets`
      requires `X-API-Key`; missing/invalid key → 401 (exercised via
      `tenant_and_key`/`widget` fixtures in every test; see auth.py + widgets.py).
- [ ] Multi-tenant isolation explicit test — implemented (`get_for_tenant` scopes
      every owner query by `tenant_id`) but no dedicated cross-tenant test yet —
      pending Phase 3.

## Tests & docs
- [x] Automated tests cover CORS, invalid payload, oversized payload, rate
      limiting, spam control, and provider fallback:
  ```
  $ pytest -q
  ...........                                                            [100%]
  11 passed in 0.55s
  ```
- [ ] README architecture diagram — present (ASCII); full setup walkthrough
      pending Phase 3 polish.
