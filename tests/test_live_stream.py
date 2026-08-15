"""
NOTE on what's tested here vs. proven live: httpx's ASGITransport (0.27.x)
fully drains a streaming ASGI response internally before returning control to
the caller — it doesn't support holding a genuinely open, never-completing
stream concurrently with another in-process request the way a real browser
or curl (separate OS processes/sockets) does. Confirmed by hand — see
BUILDLOG.md. So this file proves the broker logic and the exact wiring point
(submissions.py calls events.publish with the right payload, and only for
non-spam submissions) via unit tests and a monkeypatched spy. The actual
"open a real stream, post a real submission, watch it arrive live" proof is
a real two-process run against a real running server — see EVIDENCE.md for
that transcript.
"""

import asyncio

from app.services import events as events_service

# --- Unit tests: the broker itself ------------------------------------------


def test_publish_with_no_subscribers_does_not_raise():
    asyncio.run(events_service.publish("no-such-widget", {"x": 1}))


def test_subscribe_receives_published_event():
    async def scenario():
        queue = events_service.subscribe("widget-1")
        await events_service.publish("widget-1", {"hello": "world"})
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event == {"hello": "world"}

    asyncio.run(scenario())


def test_publish_only_reaches_subscribers_of_that_widget():
    async def scenario():
        queue_a = events_service.subscribe("widget-a")
        queue_b = events_service.subscribe("widget-b")
        await events_service.publish("widget-a", {"for": "a"})

        event = await asyncio.wait_for(queue_a.get(), timeout=1)
        assert event == {"for": "a"}
        assert queue_b.empty()

    asyncio.run(scenario())


def test_unsubscribe_removes_the_queue():
    async def scenario():
        queue = events_service.subscribe("widget-x")
        assert events_service.subscriber_count("widget-x") == 1
        events_service.unsubscribe("widget-x", queue)
        assert events_service.subscriber_count("widget-x") == 0

    asyncio.run(scenario())


# --- Auth / ownership on the stream endpoint (ordinary, non-streaming 4xx
# responses — these return before the StreamingResponse is created, so the
# ASGITransport limitation above doesn't apply to them) -------------------


def test_stream_rejects_invalid_key(client, widget):
    resp = client.get(f"/api/dashboard/widgets/{widget['id']}/stream?key=not-a-real-key")
    assert resp.status_code == 401


def test_stream_rejects_other_tenants_widget(client, widget):
    other_signup = client.post(
        "/api/auth/signup", json={"email": "other-stream@example.com", "password": "password123"}
    )
    other_key = other_signup.json()["api_key"]
    resp = client.get(f"/api/dashboard/widgets/{widget['id']}/stream?key={other_key}")
    assert resp.status_code == 404


# --- Wiring: submissions.py actually calls events.publish, with the right
# payload, and only for non-spam submissions --------------------------------


def test_valid_submission_publishes_event(client, widget, monkeypatch):
    published = {}

    async def fake_publish(widget_id, event):
        published["widget_id"] = widget_id
        published["event"] = event

    monkeypatch.setattr(events_service, "publish", fake_publish)

    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": "wired@example.com"}, "website": ""},
    )
    assert resp.status_code == 201
    assert published["widget_id"] == widget["id"]
    assert published["event"]["data"]["email"] == "wired@example.com"
    assert published["event"]["id"] == resp.json()["id"]


def test_spam_submission_does_not_publish_event(client, widget, monkeypatch):
    published = {"called": False}

    async def fake_publish(widget_id, event):
        published["called"] = True

    monkeypatch.setattr(events_service, "publish", fake_publish)

    resp = client.post(
        "/submissions",
        json={
            "widget_id": widget["id"],
            "data": {"email": "bot@example.com"},
            "website": "http://spam.example",
        },
    )
    assert resp.status_code == 201
    assert published["called"] is False


def test_publish_failure_does_not_break_the_submission(client, widget, monkeypatch):
    """Same 'never blocks the main path' rule as email/geo — a broadcast
    failure must not turn a successful submission into an error response."""

    async def failing_publish(widget_id, event):
        raise RuntimeError("simulated broadcast failure")

    monkeypatch.setattr(events_service, "publish", failing_publish)

    resp = client.post(
        "/submissions",
        json={"widget_id": widget["id"], "data": {"email": "resilient@example.com"}, "website": ""},
    )
    assert resp.status_code == 201
