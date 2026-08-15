"""
Proof-of-work bot defense (a "hashcash"-style challenge), chosen over a
CAPTCHA because it's genuinely $0/no-account (§10's iron rule) and needs no
third-party service or key.

How it works: the widget fetches a random salt + difficulty from
GET /widgets/{id}/challenge, then brute-forces a `solution` string such that
sha256(salt + solution) starts with `difficulty` zero hex characters. A real
browser does this in milliseconds via Web Crypto; a naive script bot that
just POSTs to /submissions directly has no solution at all and is rejected
outright — see scripts/measure_bot_defense.py for the measured comparison.

Same documented limitation as rate_limit.py/events.py: in-process state,
fine for a single-instance capstone demo.
"""

import hashlib
import secrets
import time
from dataclasses import dataclass

from app.config import get_settings

settings = get_settings()

CHALLENGE_TTL_SECONDS = 300


@dataclass
class Challenge:
    id: str
    widget_id: str
    salt: str
    difficulty: int
    issued_at: float
    used: bool = False


_challenges: dict[str, Challenge] = {}


def issue_challenge(widget_id: str, difficulty: int | None = None) -> Challenge:
    difficulty = settings.pow_difficulty if difficulty is None else difficulty
    challenge = Challenge(
        id=secrets.token_urlsafe(16),
        widget_id=widget_id,
        salt=secrets.token_hex(16),
        difficulty=difficulty,
        issued_at=time.time(),
    )
    _challenges[challenge.id] = challenge
    return challenge


def _prune_expired() -> None:
    now = time.time()
    expired = [cid for cid, c in _challenges.items() if now - c.issued_at > CHALLENGE_TTL_SECONDS]
    for cid in expired:
        _challenges.pop(cid, None)


def verify_and_consume(challenge_id: str, widget_id: str, solution: str) -> tuple[bool, str]:
    """Single-use: a valid solve consumes the challenge immediately, so a
    replayed (challenge_id, solution) pair — e.g. a bot that scraped one
    valid solve and tried to reuse it in a burst — fails every time after
    the first. Returns (ok, reason) so the caller can log/report why."""
    _prune_expired()

    challenge = _challenges.get(challenge_id)
    if challenge is None:
        return False, "challenge_not_found_or_expired"
    if challenge.widget_id != widget_id:
        return False, "challenge_widget_mismatch"
    if challenge.used:
        return False, "challenge_already_used"
    if time.time() - challenge.issued_at > CHALLENGE_TTL_SECONDS:
        _challenges.pop(challenge_id, None)
        return False, "challenge_expired"

    digest = hashlib.sha256((challenge.salt + solution).encode()).hexdigest()
    if not digest.startswith("0" * challenge.difficulty):
        return False, "solution_incorrect"

    challenge.used = True
    _challenges.pop(challenge_id, None)
    return True, "ok"


def reset() -> None:
    """Test helper — clears all issued challenges between test cases."""
    _challenges.clear()
