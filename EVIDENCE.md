# Evidence — one proof per Definition-of-Done checkbox (§6 of the brief)

Filled in as each checkbox goes green. Phase 1 has no runtime evidence yet —
only the design gate below.

## Design gate (Phase 1)
- [x] One-page design doc written: see `DESIGN.md` (data model, embed flow, API
      surface for all three request paths, one explicit non-goal).

## Widget management
- [ ] Authenticated CRUD; unauthenticated requests rejected — _pending Phase 2/3_
- [ ] Multi-tenant isolation proven — _pending_

## Widget delivery
- [ ] Config endpoint returns correct cache headers — _pending_
- [ ] Widget JS served as a versioned bundle — _pending_
- [ ] Widget renders on a second-origin page — _pending_

## Public submission API
- [ ] Cross-origin submission works (CORS + preflight) — _pending_
- [ ] Malformed/oversized payload → clean 4xx — _pending_

## Abuse protection
- [ ] Rate limiting returns 429 under burst, service stays up — _pending_
- [ ] Honeypot blocks a spam submission — _pending_

## Enrichment & safe side effects
- [ ] Provider A down → provider B answers — _pending_
- [ ] Both down → submission still stored — _pending_
- [ ] Failing email/webhook doesn't block the submission — _pending_

## Tests & docs
- [ ] Automated tests cover CORS/invalid/oversized/rate-limit/spam/fallback — _pending_
- [ ] README with architecture diagram + setup — _pending_
