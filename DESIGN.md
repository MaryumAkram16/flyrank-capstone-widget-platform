# Design Doc — Embeddable Widget & Lead-Capture Platform

Stack: Python + FastAPI · SQLite (via SQLAlchemy) · plain HTML/JS test page as the "customer site"
Widget types in scope: **signup form**, **CTA popover**

## 1. Problem

Customers need to collect leads from websites they don't control, without building
a form backend themselves. They configure a widget once, paste a one-line
`<script>` tag anywhere, and every visitor submission has to be validated, rate
limited, spam-filtered, geo-enriched, stored, and surfaced in a dashboard — even
though the request can come from any origin, any client, any intent.

## 2. Data model

**`tenants`** (owner/customer account)
- `id` (uuid, pk)
- `email` (unique)
- `hashed_password`
- `api_key` (for authenticated calls — issued at signup)
- `created_at`

**`widgets`**
- `id` (uuid, pk)
- `tenant_id` (fk → tenants.id, indexed) — every query is scoped to this
- `type` (enum: `signup_form` | `cta_popover`)
- `title`, `description`
- `fields` (JSON — ordered list of `{name, label, type, required}`; type ∈ text/email/textarea/checkbox)
- `button_text`
- `display_options` (JSON — e.g. `{position, theme, delay_seconds}`, mainly used by `cta_popover`)
- `config_version` (int, bumped on every edit — drives cache-busting for `/widgets/{id}/config`)
- `bundle_version` (string, e.g. `v1` — drives the versioned `widget.js` URL)
- `created_at`, `updated_at`

Index: `(tenant_id)`, unique `(tenant_id, id)` for isolation checks.

**`submissions`**
- `id` (uuid, pk)
- `widget_id` (fk → widgets.id, indexed)
- `tenant_id` (denormalized from the widget at write time — lets every dashboard
  query filter by tenant without a join, and makes the isolation check a single
  `WHERE` clause)
- `data` (JSON — the submitted field values, keyed by field name)
- `ip_address`
- `geo_country`, `geo_city`, `geo_provider` (which of A/B answered, or null)
- `is_spam` (bool — true if honeypot tripped; still logged, never shown as a lead)
- `email_sent` (bool — best-effort side-effect status, never blocks the write)
- `created_at`

Index: `(tenant_id, widget_id, created_at)` — the shape every dashboard query needs
(per-widget, time-ordered, tenant-scoped).

## 3. The embed flow

1. Tenant authenticates and `POST /api/widgets` → gets back a `widget_id` and the
   ready-to-paste snippet: `<script src=".../widget.js?id={id}"></script>`.
2. Customer pastes that one line into any page, any origin.
3. Browser loads `GET /widget.js` — a static, versioned bundle (`Cache-Control:
   immutable, max-age=1y`; the URL changes on release, not the content).
4. The bundle reads `id` from its own `<script>` tag, then calls
   `GET /widgets/{id}/config` (public, CORS `*`, short cache — `max-age=60`) to
   get title/fields/button/display options and renders the form or popover.
5. Visitor submits → `POST /submissions` (public, CORS restricted to the origins
   the tenant registered, or `*` if none registered) with `{widget_id, data,
   honeypot_field}`.
6. Backend pipeline: validate → rate-limit + honeypot check → geo-enrich (provider
   A → provider B → none) → store → best-effort confirmation email (log-only) →
   `2xx`. Every failure after "store" is swallowed; only pre-store failures
   produce a 4xx/429.
7. Tenant views `GET /api/dashboard/widgets/{id}/stats` and `/submissions`
   (authenticated, tenant-scoped).

## 4. API surface (three paths, kept structurally separate)

**A. Owner path — authenticated, `/api/...`**
- `POST /api/widgets` · `GET /api/widgets` · `GET/PATCH/DELETE /api/widgets/{id}`
- `GET /api/dashboard/widgets/{id}/submissions`
- `GET /api/dashboard/widgets/{id}/stats`

**B. Delivery path — public, cached**
- `GET /widget.js` — versioned bundle
- `GET /widgets/{id}/config` — public, CORS `*`, short TTL

**C. Submission path — public, hardened**
- `POST /submissions` — CORS-restricted, validated, rate-limited, spam-checked
- `OPTIONS /submissions` — preflight, handled explicitly

## 5. Layering

`routers/` (HTTP + status codes) → `services/` (business rules: rate limit, spam,
enrichment fallback, side effect) → `repositories/` (SQLAlchemy queries, always
tenant-scoped) → `models/` (SQLAlchemy + Pydantic schemas). The DB and the geo
providers are both swappable behind an interface so Phase 2's provider fallback
chain and Phase 3's Postgres option don't touch route code.

## 6. Non-goal

**No visual/drag-and-drop widget builder.** Widgets are configured via the JSON
API only; the rendered widget itself is a minimal, unstyled form/popover. Theming
and a form-builder UI are explicitly out of scope for this capstone.
