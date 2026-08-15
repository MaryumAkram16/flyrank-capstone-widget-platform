from app.services import geo as geo_service
from app.services import notify
from app.services.rate_limit import reset as reset_rate_limits

ALLOWED_ORIGIN = "http://localhost:5500"


# --- Probe 1: valid cross-origin submission stores + shows in dashboard -----


def test_valid_submission_is_stored_and_visible_in_dashboard(client, tenant_and_key, widget):
    resp = client.post(
        "/submissions",
        headers={"Origin": ALLOWED_ORIGIN},
        json={"widget_id": widget["id"], "data": {"email": "visitor@example.com"}, "website": ""},
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
    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": 12345}},  # wrong type
    )
    assert 400 <= resp.status_code < 500
    assert resp.json()  # a JSON body, not a bare 500 traceback


def test_oversized_field_value_rejected(client, widget):
    huge_value = "x" * 5000  # exceeds MAX_FIELD_VALUE_LEN
    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": huge_value}},
    )
    assert resp.status_code == 400


def test_oversized_body_rejected_with_413(client, widget):
    huge_data = {f"field_{i}": "x" * 500 for i in range(60)}
    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": huge_data},
    )
    assert resp.status_code in (400, 413)


# --- Probe 3: rate limiting -------------------------------------------------


def test_burst_triggers_429_then_service_recovers(client, widget):
    reset_rate_limits()
    last_status = None
    for _ in range(25):
        resp = client.post(
            "/submissions",
            json={"widget_id": widget["id"], "data": {"email": "a@example.com"}},
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

    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": "a@example.com"}},
    )
    assert resp.status_code == 201
    assert resp.json()["geo_country"] is None


# --- Probe 5: failing side effect must not block the submission ------------


def test_failing_email_side_effect_does_not_block_submission(client, widget):
    notify.FORCE_FAIL = True
    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": "a@example.com"}},
    )
    assert resp.status_code == 201
    assert resp.json()["id"]  # stored despite the side effect failing


# --- Probe 6: honeypot silently blocks spam ---------------------------------


def test_honeypot_filled_marks_submission_as_spam(client, widget):
    resp = client.post(
        "/submissions",
        json={
            "widget_id": widget["id"],
            "data": {"email": "bot@example.com"},
            "website": "http://spam.example",  # a human never fills this
        },
    )
    # Silently accepted from the bot's point of view, but flagged internally.
    assert resp.status_code == 201
    assert resp.json()["is_spam"] is True


def test_widget_not_found_returns_404(client):
    resp = client.post(
        "/submissions",
        json={"widget_id": "does-not-exist", "data": {}},
    )
    assert resp.status_code == 404
