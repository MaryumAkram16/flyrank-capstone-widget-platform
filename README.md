# Embeddable Widget & Lead-Capture Platform

FlyRank Backend Track capstone. Lets a tenant define a widget (signup form or
CTA popover), embed it anywhere with one `<script>` tag, and safely collect,
protect, enrich, and dashboard every submission from the open internet.

Full design rationale: see [`DESIGN.md`](./DESIGN.md).

## Status

- [x] Phase 1 — Design doc
- [ ] Phase 2 — Hardened submission path (in progress)
- [ ] Phase 3 — Delivery, dashboard & proof
- [ ] Phase 4 — Demo prep

## Architecture

```
Widget Owner (authenticated)
 └─► Widget Management API ─► Widget DB (tenant-isolated) ─► embed snippet

Customer Website (any origin)
 └─ <script src="widget.js?id=123">
    └─► GET /widgets/:id/config (public · cached · CORS)
    └─► render widget

Website Visitor
 └─► POST /submissions (public · CORS)
      ├─► validation ── bad payload? → 4xx, never 500
      ├─► rate limit + spam check ── flood? → 429, service stays up
      ├─► geo enrichment: Provider A ─(fails)─► Provider B ─(fails)─► store anyway
      ├─► store submission
      └─► email/webhook side effect (failure must NOT block success)

Widget Owner (authenticated)
 └─► Dashboard API ◄── submissions + stats
```

## Setup

```bash
git clone <this repo>
cd flyrank-capstone-widget-platform
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python -m app.seed
uvicorn app.main:app --reload
```

Open `test-site/index.html` (a separate local origin, e.g.
`python -m http.server 5500` from `test-site/`) to see the widget render on a
page the API doesn't serve.

## Limitations

Documented honestly as each phase lands — see `EVIDENCE.md` for what's proven
and `BUILDLOG.md` for how AI was used.
