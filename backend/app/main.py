from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

from app.database import Base, engine

from app.routes.auth import router as auth_router
from app.routes.files import router as files_router
from app.routes.admin import router as admin_router

# ─── CREATE TABLES ───────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# Repo layout: backend/app/main.py → parents[2] = CloudVault
REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_INDEX = REPO_ROOT / "frontend" / "index.html"

# ─── APP INIT ────────────────────────────────────────────────────────────
app = FastAPI(title="CloudVault API", version="2.0.0")

# ─── CORS ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # ⚠️ tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API ROUTES ──────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(files_router)
app.include_router(admin_router)

# ─── UPLOAD STORAGE ───────────────────────────────────────────────────────
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ─── FRONTEND (same process as API; open http://localhost:8000/) ────────────
@app.get("/", include_in_schema=False)
def serve_frontend():
    if not FRONTEND_INDEX.is_file():
        return {
            "error": "frontend/index.html not found",
            "expected": str(FRONTEND_INDEX),
        }
    return FileResponse(FRONTEND_INDEX)