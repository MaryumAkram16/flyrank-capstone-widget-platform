# Demo script — 6 minutes, mapped to §13 of the brief

Rehearsed end-to-end against a running server (see `EVIDENCE.md` for the
transcript). One thing below is marked **unverified in this environment** —
do that one check yourself before the real demo; everything else was proven
live.

## Setup (before the demo starts, not part of the 6 minutes)

```bash
# terminal 1
cp .env.example .env
python -m app.seed
# copy the printed API key, signup-form widget id, and CTA-popover widget id
uvicorn app.main:app --reload

# terminal 2
cd test-site
python -m http.server 5500
```

Edit `test-site/index.html`: replace `PASTE_WIDGET_ID_HERE` with the seeded
signup-form widget id. Open `http://localhost:5500` in a browser tab, and keep
a second tab open on `http://localhost:8000/docs` (FastAPI's auto-generated
API explorer — faster to click through live than typing curl on stage).

Set two shell variables so the commands below are copy-paste ready:
```bash
export KEY=<the API key the seed step printed>
export WID=<the signup-form widget id the seed step printed>
```

---

## Beat 1 — Create a widget, show the snippet (≈45s)

```bash
curl -s -X POST http://localhost:8000/api/widgets -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"type":"cta_popover","title":"Get 10% off","fields":[{"name":"email","label":"Email","type":"email","required":true}]}' \
  | python3 -m json.tool
```
Point at `embed_snippet` in the response — that's the one line a customer
pastes anywhere.

## Beat 2 — Show it rendering on a page you don't own (≈45s)

Switch to the `http://localhost:5500` browser tab. It's served by a
completely different process on a different port than the API — open dev
tools' Network tab and point out the `widget/v1.js` and `.../config` requests
going to `:8000` while the page itself came from `:5500`.

## Beat 3 — Submit, show it land in the dashboard (≈45s)

Fill the visible form on the test-site page and submit, or:
```bash
curl -s -X POST http://localhost:8000/submissions -H "Content-Type: application/json" \
  -d "{\"widget_id\":\"$WID\",\"data\":{\"email\":\"visitor@example.com\"}}"

curl -s http://localhost:8000/api/dashboard/widgets/$WID/stats -H "X-API-Key: $KEY" \
  | python3 -m json.tool
```

## Beat 4 — Attack yourself (≈60s)

```bash
# invalid payload -> clean 4xx, not a 500
curl -s -o /dev/null -w "invalid payload: %{http_code}\n" -X POST http://localhost:8000/submissions \
  -H "Content-Type: application/json" -d "{\"widget_id\":\"$WID\",\"data\":{\"email\":12345}}"

# disallowed origin -> CORS doesn't echo the origin back
curl -s -D - -o /dev/null http://localhost:8000/submissions -X OPTIONS \
  -H "Origin: http://evil.example" -H "Access-Control-Request-Method: POST" \
  | grep -i "access-control-allow-origin\|HTTP/1.1"

# burst -> 429 mid-way through
for i in $(seq 1 22); do
  curl -s -o /dev/null -w "%{http_code} " -X POST http://localhost:8000/submissions \
    -H "Content-Type: application/json" -d "{\"widget_id\":\"$WID\",\"data\":{\"email\":\"burst$i@example.com\"}}"
done; echo
```

**Immediately after this beat**, reset so the burst doesn't bleed into the
next two beats:
```bash
curl -s -X POST http://localhost:8000/demo/reset
```

## Beat 5 — Kill the primary geo provider live (≈60s)

```bash
curl -s -X POST http://localhost:8000/demo/geo-provider-a/down

curl -s -X POST http://localhost:8000/submissions -H "Content-Type: application/json" \
  -H "X-Forwarded-For: 8.8.8.8" \
  -d "{\"widget_id\":\"$WID\",\"data\":{\"email\":\"fallback-demo@example.com\"}}" \
  | python3 -m json.tool
```
Point at `geo_country`/`geo_city` in the response — provider A is forced down,
so this came from provider B. **⚠ Unverified in the sandbox I built this in**:
outbound calls to `ip-api.com`/`ipapi.co` are blocked by my sandbox's network
policy, so I only confirmed the *fallback logic itself* (via the mocked test
`test_provider_a_down_falls_back_to_provider_b`), not real geo data coming
back live. Run this exact command on your machine before the real demo and
confirm `geo_country`/`geo_city` are populated — if they're not, provider B's
free-tier rate limit may be the cause; wait a minute and retry.

```bash
curl -s -X POST http://localhost:8000/demo/reset
```

## Beat 6 — Break the email side effect (≈45s)

```bash
curl -s -X POST http://localhost:8000/demo/email-side-effect/failing

curl -s -o /dev/null -w "status: %{http_code}\n" -X POST http://localhost:8000/submissions \
  -H "Content-Type: application/json" -d "{\"widget_id\":\"$WID\",\"data\":{\"email\":\"sideeffect-demo@example.com\"}}"

curl -s -X POST http://localhost:8000/demo/reset
```
Say the line: **"non-critical failures never break the main path."** Status
was `201` even with the email side effect forced to throw — confirmed live in
this environment (see `EVIDENCE.md`).

## Beat 7 — Close on the dashboard (≈40s)

```bash
curl -s http://localhost:8000/api/dashboard/widgets/$WID/stats -H "X-API-Key: $KEY" \
  | python3 -m json.tool
```
Total submissions, spam blocked, geo coverage — everything the visitor
triggered across beats 3–6, in one view.

---

## Why this failure (provider fallback) over the others

The brief only asks you to show *one* failure live. Provider A→B fallback was
picked over the email side-effect failure because it's the more visually
convincing "degrade, never fail" moment — a `geo_country` field visibly
changing from populated to still-populated-via-B, versus an email failure
that's invisible unless you're staring at a log line. Both are wired and
tested either way (`/demo/*` toggles both), so you can swap which one you
narrate live without any extra prep.
