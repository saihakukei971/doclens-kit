# app/main.py
from fastapi import FastAPI, UploadFile, File, Form, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.logger import log
from app.api import documents, search, system

# Create FastAPI application
app = FastAPI(
    title="業務データ統合ハブ",
    description="企業内文書管理・検索システム",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Properly restrict in production environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files configuration
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

# Routing
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(system.router, prefix="/api/system", tags=["system"])

# Startup event
@app.on_event("startup")
async def startup():
    log.info("アプリケーション起動中...")
    # Check data directories
    os.makedirs("data/documents", exist_ok=True)
    os.makedirs("data/archives", exist_ok=True)

    # DB initialization
    await init_db()
    log.info("データベース初期化完了")
    log.info("アプリケーション起動完了")

# Shutdown event
@app.on_event("shutdown")
async def shutdown():
    log.info("アプリケーション終了中...")
    await close_db()
    log.info("アプリケーション終了完了")

# Root path
@app.get("/")
async def root():
    return {"message": "業務データ統合ハブAPI", "status": "running"}

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}