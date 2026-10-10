"""
HackInterview Backend — FastAPI entry point
============================================
Slim entry point: initialises the app, middleware, static files, service
singletons, and wires up all APIRouters.
"""
import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import logger, STATIC_DIR, STATIC_OUTPUT_DIR

# -------------------------------------------------------------------
# App
# -------------------------------------------------------------------
app = FastAPI(title="HackInterview API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# -------------------------------------------------------------------
# Service singletons (initialised once at startup)
# -------------------------------------------------------------------
try:
    from voice_service import VoiceService
    voice_service = VoiceService()
    logger.info("VoiceService initialised")
except Exception as e:
    voice_service = None
    logger.warning(f"VoiceService unavailable: {e}")

try:
    from avatar_service import AvatarService
    avatar_service = AvatarService()
    logger.info("AvatarService initialised")
except Exception as e:
    avatar_service = None
    logger.warning(f"AvatarService unavailable: {e}")

try:
    from vision_service import VisionService
    vision_service = VisionService()
    logger.info("VisionService initialised")
except Exception as e:
    vision_service = None
    logger.warning(f"VisionService unavailable: {e}")

# -------------------------------------------------------------------
# Register routers
# -------------------------------------------------------------------
from routes.auth import router as auth_router
from routes.interview import router as interview_router
from routes.resume import router as resume_router
from routes.voice import router as voice_router
from routes.vision import router as vision_router
from routes.avatar import router as avatar_router
from routes.tokens import router as tokens_router
from routes.posture import router as posture_router
from routes.assessment import router as assessment_router
from routes.admin_assessment import router as admin_assessment_router
from routes.institution import router as institution_router

app.include_router(auth_router)
app.include_router(interview_router)
app.include_router(resume_router)
app.include_router(voice_router)
app.include_router(vision_router)
app.include_router(avatar_router)
app.include_router(tokens_router)
app.include_router(posture_router)
app.include_router(assessment_router)
app.include_router(admin_assessment_router)
app.include_router(institution_router)

# -------------------------------------------------------------------
# Health-check
# -------------------------------------------------------------------
@app.get("/")
async def root():
    return {"message": "HackInterview API is running", "status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
