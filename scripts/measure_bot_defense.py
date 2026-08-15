"""
Measures the actual spam reduction from the proof-of-work bot defense, per
§9's ask: "bot defense: ... measure the spam reduction."

Simulates two attacker profiles against a real running server:
  1. "Naive bot" — the pre-feature threat model: fires raw POSTs straight at
     /submissions with no challenge at all, exactly what a bot did before
     this stretch goal existed (it would previously have been stored,
     possibly caught by the honeypot, possibly not).
  2. "Scripted attacker" — a slightly more sophisticated bot that fetches a
     real challenge but guesses at a solution instead of brute-forcing one
     (representing an attacker who noticed the endpoint but didn't implement
     the actual proof-of-work).

Then, for comparison, a "legitimate visitor" profile that solves the
challenge properly (the same algorithm the widget bundle runs client-side).

Usage:
    python -m app.seed                      # get a widget id + api key printed
    uvicorn app.main:app --reload            # in one terminal
    python scripts/measure_bot_defense.py <widget_id>   # in another
"""

import hashlib
import sys
import time

import httpx

BASE_URL = "http://localhost:8000"
ATTEMPTS_PER_PROFILE = 20


def naive_bot_attempt(client: httpx.Client, widget_id: str) -> int:
    resp = client.post(
        f"{BASE_URL}/submissions",
        json={"widget_id": widget_id, "data": {"email": "naive-bot@example.com"}},
    )
    return resp.status_code


def scripted_attacker_attempt(client: httpx.Client, widget_id: str) -> int:
    resp = client.post(
        f"{BASE_URL}/submissions",
        json={
            "widget_id": widget_id,
            "data": {"email": "scripted-bot@example.com"},
            "challenge_id": "guessed-id-not-real",
            "solution": "0",
        },
    )
    return resp.status_code


def legitimate_visitor_attempt(client: httpx.Client, widget_id: str) -> int:
    challenge = client.get(f"{BASE_URL}/widgets/{widget_id}/challenge").json()
    salt = challenge["salt"]
    prefix = "0" * challenge["difficulty"]
    counter = 0
    while True:
        solution = str(counter)
        if hashlib.sha256((salt + solution).encode()).hexdigest().startswith(prefix):
            break
        counter += 1

    resp = client.post(
        f"{BASE_URL}/submissions",
        json={
            "widget_id": widget_id,
            "data": {"email": "real-visitor@example.com"},
            "challenge_id": challenge["challenge_id"],
            "solution": solution,
        },
    )
    return resp.status_code


def run_profile(name: str, fn, client: httpx.Client, widget_id: str, n: int) -> None:
    # Clear rate-limit counters before each profile so the rate limiter
    # (a separate defense layer, already measured in EVIDENCE.md) doesn't
    # confound this specific measurement.
    client.post(f"{BASE_URL}/demo/reset")

    succeeded = 0
    start = time.time()
    for _ in range(n):
        status = fn(client, widget_id)
        if status == 201:
            succeeded += 1
    elapsed = time.time() - start
    blocked = n - succeeded
    print(
        f"{name:22s} {succeeded:3d}/{n} succeeded  "
        f"({blocked}/{n} blocked, {100 * blocked / n:.0f}% block rate)  "
        f"[{elapsed:.2f}s]"
    )


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/measure_bot_defense.py <widget_id>")
        sys.exit(1)
    widget_id = sys.argv[1]

    with httpx.Client() as client:
        health = client.get(f"{BASE_URL}/health")
        if health.status_code != 200:
            print(f"Server not reachable at {BASE_URL} — start it with `uvicorn app.main:app --reload`")
            sys.exit(1)

        print(f"Measuring against widget {widget_id}, {ATTEMPTS_PER_PROFILE} attempts per profile\n")
        run_profile("Naive bot", naive_bot_attempt, client, widget_id, ATTEMPTS_PER_PROFILE)
        run_profile("Scripted attacker", scripted_attacker_attempt, client, widget_id, ATTEMPTS_PER_PROFILE)
        run_profile("Legitimate visitor", legitimate_visitor_attempt, client, widget_id, ATTEMPTS_PER_PROFILE)


if __name__ == "__main__":
    main()
