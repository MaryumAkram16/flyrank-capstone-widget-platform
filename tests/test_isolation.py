"""
Proves tenant A can never read, edit, delete, or see stats for tenant B's
widgets or submissions — the isolation guarantee §6/§7 of the brief calls out
by name, and the one gap Phase 2's EVIDENCE.md left open.
"""

from conftest import solve_pow_challenge


def _signup_and_widget(client, email):
    signup = client.post("/api/auth/signup", json={"email": email, "password": "password123"})
    assert signup.status_code == 201
    api_key = signup.json()["api_key"]

    created = client.post(
        "/api/widgets",
        headers={"X-API-Key": api_key},
        json={
            "type": "signup_form",
            "title": f"Widget for {email}",
            "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}],
        },
    )
    assert created.status_code == 201
    return api_key, created.json()["id"]


def test_tenant_cannot_read_another_tenants_widget(client):
    key_a, widget_a_id = _signup_and_widget(client, "a@example.com")
    key_b, widget_b_id = _signup_and_widget(client, "b@example.com")

    resp = client.get(f"/api/widgets/{widget_b_id}", headers={"X-API-Key": key_a})
    assert resp.status_code == 404


def test_tenant_cannot_edit_another_tenants_widget(client):
    key_a, _ = _signup_and_widget(client, "a2@example.com")
    key_b, widget_b_id = _signup_and_widget(client, "b2@example.com")

    resp = client.patch(
        f"/api/widgets/{widget_b_id}",
        headers={"X-API-Key": key_a},
        json={"title": "Hijacked"},
    )
    assert resp.status_code == 404


def test_tenant_cannot_delete_another_tenants_widget(client):
    key_a, _ = _signup_and_widget(client, "a3@example.com")
    key_b, widget_b_id = _signup_and_widget(client, "b3@example.com")

    resp = client.delete(f"/api/widgets/{widget_b_id}", headers={"X-API-Key": key_a})
    assert resp.status_code == 404

    # And it's still there for its real owner.
    still_there = client.get(f"/api/widgets/{widget_b_id}", headers={"X-API-Key": key_b})
    assert still_there.status_code == 200


def test_widget_list_never_shows_another_tenants_widgets(client):
    key_a, widget_a_id = _signup_and_widget(client, "a4@example.com")
    key_b, widget_b_id = _signup_and_widget(client, "b4@example.com")

    listing = client.get("/api/widgets", headers={"X-API-Key": key_a}).json()
    ids = [w["id"] for w in listing]
    assert widget_a_id in ids
    assert widget_b_id not in ids


def test_dashboard_stats_and_submissions_scoped_per_tenant(client):
    key_a, widget_a_id = _signup_and_widget(client, "a5@example.com")
    key_b, widget_b_id = _signup_and_widget(client, "b5@example.com")

    # A visitor submits to B's widget.
    pow_fields = solve_pow_challenge(client, widget_b_id)
    client.post(
        "/submissions",
        json={
            "widget_id": widget_b_id,
            "data": {"email": "visitor@example.com"},
            "website": "",
            **pow_fields,
        },
    )

    # Tenant A can't see B's submissions or stats through B's widget id.
    subs = client.get(
        f"/api/dashboard/widgets/{widget_b_id}/submissions", headers={"X-API-Key": key_a}
    )
    assert subs.status_code == 404

    stats = client.get(
        f"/api/dashboard/widgets/{widget_b_id}/stats", headers={"X-API-Key": key_a}
    )
    assert stats.status_code == 404

    # But tenant B sees exactly their one submission.
    own_subs = client.get(
        f"/api/dashboard/widgets/{widget_b_id}/submissions", headers={"X-API-Key": key_b}
    )
    assert own_subs.status_code == 200
    assert len(own_subs.json()) == 1


def test_missing_api_key_is_rejected(client):
    resp = client.get("/api/widgets")
    assert resp.status_code == 401


def test_invalid_api_key_is_rejected(client):
    resp = client.get("/api/widgets", headers={"X-API-Key": "not-a-real-key"})
    assert resp.status_code == 401
