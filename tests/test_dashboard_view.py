from conftest import solve_pow_challenge


def test_dashboard_view_requires_valid_key(client, widget):
    resp = client.get(f"/api/dashboard/widgets/{widget['id']}/view")
    assert resp.status_code == 422  # key is a required query param

    resp = client.get(f"/api/dashboard/widgets/{widget['id']}/view?key=bad-key")
    assert resp.status_code == 401


def test_dashboard_view_renders_stats_and_table(client, tenant_and_key, widget):
    client.post(
        "/submissions",
        json={
            "widget_id": widget["id"],
            "data": {"email": "visitor@example.com"},
            "website": "",
            **solve_pow_challenge(client, widget["id"]),
        },
    )

    resp = client.get(
        f"/api/dashboard/widgets/{widget['id']}/view?key={tenant_and_key['api_key']}"
    )
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    body = resp.text
    assert "visitor@example.com" in body
    assert "Total submissions" in body
    assert ">1<" in body  # the total count rendered


def test_dashboard_view_escapes_submission_data(client, tenant_and_key, widget):
    """A visitor can put whatever they want in a form field. If this ever
    renders unescaped, that's stored XSS against the widget owner."""
    payload_attempt = "<script>alert(1)</script>"
    client.post(
        "/submissions",
        json={
            "widget_id": widget["id"],
            "data": {"email": payload_attempt},
            "website": "",
            **solve_pow_challenge(client, widget["id"]),
        },
    )

    resp = client.get(
        f"/api/dashboard/widgets/{widget['id']}/view?key={tenant_and_key['api_key']}"
    )
    assert resp.status_code == 200
    assert "<script>alert(1)</script>" not in resp.text
    assert "&lt;script&gt;" in resp.text


def test_dashboard_view_other_tenants_key_gets_404_for_this_widget(client, widget):
    other_signup = client.post(
        "/api/auth/signup", json={"email": "other-owner@example.com", "password": "password123"}
    )
    other_key = other_signup.json()["api_key"]

    resp = client.get(f"/api/dashboard/widgets/{widget['id']}/view?key={other_key}")
    assert resp.status_code == 404


def test_dashboard_view_empty_state(client, tenant_and_key, widget):
    resp = client.get(
        f"/api/dashboard/widgets/{widget['id']}/view?key={tenant_and_key['api_key']}"
    )
    assert resp.status_code == 200
    assert "No submissions yet" in resp.text
