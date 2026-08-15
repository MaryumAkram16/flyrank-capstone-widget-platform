import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import submissions_repo, widgets_repo
from app.schemas import SubmissionCreate, SubmissionOut
from app.services import events as events_service
from app.services import geo as geo_service
from app.services import notify
from app.services import pow as pow_service
from app.services.rate_limit import is_rate_limited
from app.services.spam import is_spam

logger = logging.getLogger("submissions")

router = APIRouter(tags=["submissions"])


def _client_ip(request: Request) -> str:
    # Respect a proxy header if present (e.g. behind a real CDN/LB later),
    # otherwise fall back to the direct connection.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/submissions",
    status_code=status.HTTP_201_CREATED,
    response_model=SubmissionOut,
)
async def create_submission(request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)

    # --- 1. validation at the boundary --------------------------------------
    # Parsed manually (not as a FastAPI body param) so a malformed JSON body
    # and an oversized field both land on the same clean-4xx path instead of
    # FastAPI's default 422 shape — the brief wants "clean 4xx JSON errors,
    # never a 500" and this keeps the error shape consistent across every
    # kind of bad input.
    try:
        raw = await request.json()
        payload = SubmissionCreate.model_validate(raw)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_payload", "message": str(exc)},
        ) from exc

    # --- 2. rate limiting — per IP and per widget, before any DB/network work
    if is_rate_limited(f"ip:{ip}") or is_rate_limited(f"widget:{payload.widget_id}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "rate_limited", "message": "Too many submissions — try again shortly."},
        )

    # --- 3. widget must exist -------------------------------------------------
    widget = widgets_repo.get_public(db, payload.widget_id)
    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "widget_not_found"},
        )

    # --- 4. bot defense — proof-of-work challenge must be solved -----------
    ok, reason = pow_service.verify_and_consume(payload.challenge_id, widget.id, payload.solution)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "bot_challenge_failed", "reason": reason},
        )

    # --- 5. spam control (honeypot) -------------------------------------------
    spam = is_spam(payload.website)

    # --- 6. enrichment — provider A -> provider B -> none, never blocks storage
    geo_result = None
    if not spam:
        try:
            geo_result = geo_service.enrich(ip)
        except Exception as exc:  # noqa: BLE001 - enrichment must never fail the request
            logger.warning("geo enrichment raised unexpectedly, continuing without geo: %s", exc)
            geo_result = None

    # --- 7. store — this is the line that must succeed no matter what above it did
    submission = submissions_repo.create(
        db,
        widget=widget,
        data=payload.data,
        ip_address=ip,
        is_spam=spam,
        geo=geo_result,
        email_sent=False,
    )

    # --- 8. safe side effect — best effort, failure never undoes the 201 -------
    if not spam:
        contact_hint = payload.data.get("email", "")
        sent = notify.send_confirmation(contact_hint, widget.title)
        if sent:
            submission.email_sent = True
            db.commit()
            db.refresh(submission)

        # --- 9. live dashboard broadcast — best effort, same "never blocks" rule
        try:
            await events_service.publish(
                widget.id,
                {
                    "id": submission.id,
                    "data": submission.data,
                    "geo_country": submission.geo_country,
                    "geo_city": submission.geo_city,
                    "created_at": submission.created_at.isoformat(),
                },
            )
        except Exception as exc:  # noqa: BLE001 - a broadcast failure must never fail the request
            logger.warning("live dashboard broadcast failed, submission still stored: %s", exc)

    return submission
