import logging
import os
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.database import init_db
from backend.api import api_router

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("email_sender_pro")

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Email Sender Pro Backend API with High Priority & Read Receipts"
)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    logger.info("Starting %s backend in %s mode...", settings.app_name, settings.environment)
    init_db()
    logger.info("Database initialization completed.")

@app.on_event("shutdown")
def shutdown_event():
    logger.info("Shutting down %s backend...", settings.app_name)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": "An unexpected error occurred."}
    )

# Include API routers
app.include_router(api_router)

@app.get("/auth/google/callback", include_in_schema=False)
@app.get("/auth/microsoft/callback", include_in_schema=False)
def desktop_oauth_callback(request: Request):
    suffix = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(url=f"/api/oauth/callback{suffix}", status_code=307)

def _desktop_dist() -> Path:
    frozen_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return frozen_root / "dist"

if os.getenv("SENDEPRO_DESKTOP") == "1" and (_desktop_dist() / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_desktop_dist() / "assets"), name="desktop-assets")

    @app.get("/", include_in_schema=False)
    def desktop_root():
        return FileResponse(_desktop_dist() / "index.html")

    @app.get("/{spa_path:path}", include_in_schema=False)
    def desktop_spa(spa_path: str):
        candidate = (_desktop_dist() / spa_path).resolve()
        if _desktop_dist().resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_desktop_dist() / "index.html")
else:
    @app.get("/")
    def root():
        return {"message": "Welcome to Email Sender Pro API. Visit /api/health for health status."}
