import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.report import router as report_router
from app.api.routes.session import router as session_router
from app.services.transcription import TranscriptionService

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the Whisper model at startup so the first session doesn't pay the load cost.
    TranscriptionService._get_model()
    yield


app = FastAPI(title="Gliss API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_router, prefix="/api/v1")
app.include_router(report_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
