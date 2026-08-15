"""
IP -> geo enrichment with a fallback chain: provider A, then provider B, then
give up and return None (submission still succeeds without geo — see
services/notify.py and routers/submissions.py for the "degrade, never fail"
pattern applied the same way).

FORCE_DOWN_A / FORCE_DOWN_B are plain module-level toggles: tests set them
directly for deterministic fallback tests, and the same switches let you kill
a provider live during the demo (§13 of the brief) without touching real
network state.
"""

import httpx

from app.config import get_settings

settings = get_settings()

FORCE_DOWN_A = False
FORCE_DOWN_B = False

TIMEOUT_SECONDS = 3.0


class GeoResult:
    def __init__(self, country: str | None, city: str | None, provider: str | None):
        self.country = country
        self.city = city
        self.provider = provider


def _call_provider_a(ip: str) -> GeoResult | None:
    if FORCE_DOWN_A:
        return None
    try:
        # ip-api.com — free, no key, 45 req/min
        resp = httpx.get(f"{settings.geo_provider_a_url}/{ip}", timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") == "fail":
            return None
        return GeoResult(country=body.get("country"), city=body.get("city"), provider="A")
    except (httpx.HTTPError, ValueError):
        return None


def _call_provider_b(ip: str) -> GeoResult | None:
    if FORCE_DOWN_B:
        return None
    try:
        # ipapi.co — free tier, no key
        resp = httpx.get(f"{settings.geo_provider_b_url}/{ip}/json/", timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        body = resp.json()
        if body.get("error"):
            return None
        return GeoResult(
            country=body.get("country_name"), city=body.get("city"), provider="B"
        )
    except (httpx.HTTPError, ValueError):
        return None


def enrich(ip: str) -> GeoResult | None:
    """Try provider A, then provider B, then give up. Never raises — a dead
    provider (or two) must never block the submission from being stored."""
    if not ip or ip in ("127.0.0.1", "testclient", "localhost"):
        # Local/dev IPs never resolve to a real location — skip the network
        # calls entirely rather than let both providers fail slowly.
        return None
    for call in (_call_provider_a, _call_provider_b):
        result = call(ip)
        if result is not None:
            return result
    return None
