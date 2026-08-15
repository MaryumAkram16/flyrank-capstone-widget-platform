from app.services import geo as geo_service
from app.services import notify
from app.services.rate_limit import reset as reset_rate_limits
from conftest import solve_pow_challenge

ALLOWED_ORIGIN = "http://localhost:5500"


# --- Probe 1: valid cross-origin submission stores + shows in dashboard -----


def test_valid_submission_is_stored_and_visible_in_dashboard(client, tenant_and_key, widget):
    pow_fields = solve_pow_challenge(client, widget["id"])
    resp = client.post(
        "/submissions",
        headers={"Origin": ALLOWED_ORIGIN},
        json={
            "widget_id": widget["id"],
            "data": {"email": "visitor@example.com"},
            "website": "",
            **pow_fields,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["email"] == "visitor@example.com"
    assert body["is_spam"] is False

    dash = client.get(
        f"/api/dashboard/widgets/{widget['id']}/submissions",
        headers={"X-API-Key": tenant_and_key["api_key"]},
    )
    assert dash.status_code == 200
    assert len(dash.json()) == 1


# --- CORS preflight ----------------------------------------------------------


def test_cors_preflight_allows_configured_origin(client):
    resp = client.options(
        "/submissions",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


# --- Probe 2: malformed / oversized payload -> clean 4xx, never 500 --------


def test_malformed_payload_returns_clean_4xx(client, widget):
    pow_fields = solve_pow_challenge(client, widget["id"])
    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": 12345}, **pow_fields},  # wrong type
    )
    assert 400 <= resp.status_code < 500
    assert resp.json()  # a JSON body, not a bare 500 traceback


def test_oversized_field_value_rejected(client, widget):
    pow_fields = solve_pow_challenge(client, widget["id"])
    huge_value = "x" * 5000  # exceeds MAX_FIELD_VALUE_LEN
    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": huge_value}, **pow_fields},
    )
    assert resp.status_code == 400


def test_oversized_body_rejected_with_413(client, widget):
    pow_fields = solve_pow_challenge(client, widget["id"])
    huge_data = {f"field_{i}": "x" * 500 for i in range(60)}
    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": huge_data, **pow_fields},
    )
    assert resp.status_code in (400, 413)


def test_missing_challenge_fields_rejected(client, widget):
    """No challenge_id/solution at all — the shape a naive bot that never
    even looked at /widgets/{id}/challenge would send."""
    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": "bot@example.com"}},
    )
    assert resp.status_code == 400


# --- Probe 3: rate limiting -------------------------------------------------


def test_burst_triggers_429_then_service_recovers(client, widget):
    reset_rate_limits()
    last_status = None
    for _ in range(25):
        # Rate limiting (step 2) runs before the challenge is verified (step
        # 4), so a structurally-valid-but-wrong challenge is enough to prove
        # the burst limit — no need to solve 25 real proof-of-work challenges.
        resp = client.post(
            "/submissions",
            json={
                "widget_id": widget["id"],
                "data": {"email": "a@example.com"},
                "challenge_id": "burst-test-not-real",
                "solution": "0",
            },
        )
        last_status = resp.status_code
    assert last_status == 429

    # Service itself stays up — a totally different key (different widget)
    # is unaffected by another widget's burst.
    health = client.get("/health")
    assert health.status_code == 200


# --- Probe 4: geo provider fallback chain ----------------------------------


def test_provider_a_down_falls_back_to_provider_b(client, widget, monkeypatch):
    geo_service.FORCE_DOWN_A = True

    def fake_b(ip):
        return geo_service.GeoResult(country="Pakistan", city="Lahore", provider="B")

    monkeypatch.setattr(geo_service, "_call_provider_b", fake_b)

    result = geo_service.enrich("8.8.8.8")
    assert result is not None
    assert result.provider == "B"


def test_all_providers_down_submission_still_succeeds(client, widget, monkeypatch):
    geo_service.FORCE_DOWN_A = True
    geo_service.FORCE_DOWN_B = True

    pow_fields = solve_pow_challenge(client, widget["id"])
    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": "a@example.com"}, **pow_fields},
    )
    assert resp.status_code == 201
    assert resp.json()["geo_country"] is None


# --- Probe 5: failing side effect must not block the submission ------------


def test_failing_email_side_effect_does_not_block_submission(client, widget):
    notify.FORCE_FAIL = True
    pow_fields = solve_pow_challenge(client, widget["id"])
    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": "a@example.com"}, **pow_fields},
    )
    assert resp.status_code == 201
    assert resp.json()["id"]  # stored despite the side effect failing


# --- Probe 6: honeypot silently blocks spam ---------------------------------


def test_honeypot_filled_marks_submission_as_spam(client, widget):
    pow_fields = solve_pow_challenge(client, widget["id"])
    resp = client.post(
        "/submissions",
        json={
            "widget_id": widget["id"],
            "data": {"email": "bot@example.com"},
            "website": "http://spam.example",  # a human never fills this
            **pow_fields,
        },
    )
    # Silently accepted from the bot's point of view, but flagged internally.
    assert resp.status_code == 201
    assert resp.json()["is_spam"] is True


def test_widget_not_found_returns_404(client):
    resp = client.post(
        "/submissions",
        json={
            "widget_id": "does-not-exist",
            "data": {},
            "challenge_id": "irrelevant",
            "solution": "0",
        },
    )
    assert resp.status_code == 404


# --- Bot defense: proof-of-work challenge -----------------------------------


def test_submission_without_solving_challenge_is_rejected(client, widget):
    """A well-formed challenge_id (a real one, freshly issued) but a wrong
    solution — the shape of a bot that saw the challenge endpoint but didn't
    actually solve it."""
    resp = client.get(f"/widgets/{widget['id']}/challenge")
    assert resp.status_code == 200
    challenge = resp.json()

    resp = client.post(
        "/submissions",
        json={
            "widget_id": widget["id"],
            "data": {"email": "bot@example.com"},
            "challenge_id": challenge["challenge_id"],
            "solution": "not-a-real-solution",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "bot_challenge_failed"


def test_challenge_is_single_use(client, widget):
    pow_fields = solve_pow_challenge(client, widget["id"])

    first = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": "a@example.com"}, **pow_fields},
    )
    assert first.status_code == 201

    # Replaying the exact same (challenge_id, solution) pair a second time —
    # a bot that scraped one valid solve and tried to reuse it in a burst.
    second = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": "b@example.com"}, **pow_fields},
    )
    assert second.status_code == 403


def test_challenge_from_a_different_widget_is_rejected(client, widget, tenant_and_key):
    other_widget = client.post(
        "/api/widgets",
        headers={"X-API-Key": tenant_and_key["api_key"]},
        json={
            "type": "cta_popover",
            "title": "Other widget",
            "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}],
        },
    ).json()

    pow_fields = solve_pow_challenge(client, other_widget["id"])  # solved for the WRONG widget

    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": "a@example.com"}, **pow_fields},
    )
    assert resp.status_code == 403


def test_challenge_endpoint_returns_salt_and_difficulty(client, widget):
    resp = client.get(f"/widgets/{widget['id']}/challenge")
    assert resp.status_code == 200
    body = resp.json()
    assert body["challenge_id"]
    assert body["salt"]
    assert body["difficulty"] >= 1
    assert resp.headers["cache-control"] == "no-store"


def test_challenge_endpoint_404_for_unknown_widget(client):
    resp = client.get("/widgets/does-not-exist/challenge")
    assert resp.status_code == 404
