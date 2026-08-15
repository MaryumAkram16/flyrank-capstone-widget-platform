"""Run with: python -m app.seed"""

from app import models  # noqa: F401
from app.database import Base, SessionLocal, engine
from app.models import Tenant, Widget

DEMO_EMAIL = "demo@flyrank.dev"


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.email == DEMO_EMAIL).first()
        if not tenant:
            tenant = Tenant(email=DEMO_EMAIL, hashed_password="seed-only-not-a-real-hash")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)

        if not db.query(Widget).filter(Widget.tenant_id == tenant.id).first():
            signup = Widget(
                tenant_id=tenant.id,
                type="signup_form",
                title="Join our newsletter",
                description="One email a week, no spam.",
                fields=[
                    {"name": "email", "label": "Email", "type": "email", "required": True},
                ],
                button_text="Subscribe",
            )
            popover = Widget(
                tenant_id=tenant.id,
                type="cta_popover",
                title="Get 10% off",
                description="First order only.",
                fields=[
                    {"name": "email", "label": "Email", "type": "email", "required": True},
                ],
                button_text="Claim discount",
                display_options={"position": "bottom-right", "delay_seconds": 3},
            )
            db.add_all([signup, popover])
            db.commit()
            db.refresh(signup)
            db.refresh(popover)
            print(f"Tenant API key: {tenant.api_key}")
            print(f"Signup form widget id: {signup.id}")
            print(f"CTA popover widget id: {popover.id}")
        else:
            print(f"Tenant API key: {tenant.api_key}")
            print("Widgets already seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
