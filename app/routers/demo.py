"""
Demo-only control surface — NOT part of the product surface a real customer
would ever see. Exists so the two "kill a dependency live" probes in §12
(provider A down, email side effect throwing) can be triggered against a
*running* server without editing code and restarting.

If this were going further than a local capstone demo, this router would be
gated behind the same X-API-Key auth as the owner path, or removed entirely
in favor of a feature-flag service. Documented here rather than hidden.
"""

from fastapi import APIRouter

from app.services import geo as geo_service
from app.services import notify
from app.services.rate_limit import reset as reset_rate_limits

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/geo-provider-a/{state}")
def toggle_provider_a(state: str):
    geo_service.FORCE_DOWN_A = state == "down"
    return {"provider": "A", "forced_down": geo_service.FORCE_DOWN_A}


@router.post("/geo-provider-b/{state}")
def toggle_provider_b(state: str):
    geo_service.FORCE_DOWN_B = state == "down"
    return {"provider": "B", "forced_down": geo_service.FORCE_DOWN_B}


@router.post("/email-side-effect/{state}")
def toggle_email_side_effect(state: str):
    notify.FORCE_FAIL = state == "failing"
    return {"side_effect": "email", "forced_failing": notify.FORCE_FAIL}


@router.post("/reset")
def reset_all_toggles():
    """Clears failure toggles AND rate-limit counters — use this between demo
    beats (e.g. right after showing the 429 burst) so an earlier beat's rate
    limiting doesn't bleed into and mask the next beat's behavior."""
    geo_service.FORCE_DOWN_A = False
    geo_service.FORCE_DOWN_B = False
    notify.FORCE_FAIL = False
    reset_rate_limits()
    return {"reset": True}


@router.get("/status")
def toggle_status():
    return {
        "geo_provider_a_down": geo_service.FORCE_DOWN_A,
        "geo_provider_b_down": geo_service.FORCE_DOWN_B,
        "email_side_effect_failing": notify.FORCE_FAIL,
    }
