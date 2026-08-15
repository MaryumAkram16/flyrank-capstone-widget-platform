from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import models  # noqa: F401 - registers models on Base before create_all
from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, dashboard, demo, public, submissions, widgets

settings = get_settings()

MAX_BODY_BYTES = 20_000  # generous for a form submission, small enough to reject abuse fast


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Embeddable Widget & Lead-Capture Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def reject_oversized_bodies(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_BYTES:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"error": "payload_too_large", "message": f"Body exceeds {MAX_BODY_BYTES} bytes"},
        )
    return await call_next(request)


app.include_router(auth.router)
app.include_router(widgets.router)
app.include_router(public.router)
app.include_router(submissions.router)
app.include_router(dashboard.router)
app.include_router(demo.router)


@app.get("/health")
def health():
    return {"status": "ok"}
