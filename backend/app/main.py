from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import init_db
from .routes import (
    auth, factory, production, carbon, water_energy, chemicals, reports,
    dashboard, audit, ocr, verify, products, orders, batches, inventory,
    reconciliation, suppliers, lifecycle,
)

# Create FastAPI app
app = FastAPI(
    title="GreenThread API",
    description="Sustainability data management platform for textile manufacturers",
    version="1.0.0"
)

# CORS middleware - allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(factory.router, prefix="/api")
app.include_router(production.router, prefix="/api")
app.include_router(carbon.router, prefix="/api")
app.include_router(water_energy.router, prefix="/api")
app.include_router(chemicals.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(ocr.router, prefix="/api")
app.include_router(verify.router, prefix="/api")
app.include_router(products.router, prefix="/api")
# Phase 2 — batch-level production reality & allocation
app.include_router(orders.router, prefix="/api")
app.include_router(orders.share_router, prefix="/api")     # public, login-free
app.include_router(batches.router, prefix="/api")
app.include_router(batches.jobworker_router, prefix="/api")
app.include_router(batches.jobwork_router, prefix="/api")  # public, login-free
app.include_router(inventory.router, prefix="/api")
app.include_router(inventory.stock_router, prefix="/api")
app.include_router(reconciliation.router, prefix="/api")
# Phase 3 — life cycle, supply chain, digital product passports
app.include_router(lifecycle.router, prefix="/api")
app.include_router(lifecycle.passport_router, prefix="/api")          # public, login-free
app.include_router(lifecycle.media_router, prefix="/api")            # public product photos
app.include_router(suppliers.router, prefix="/api")
app.include_router(suppliers.supplier_data_router, prefix="/api")    # public, login-free


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup; seed the demo factory if asked."""
    init_db()
    if settings.DEMO_SEED:
        _seed_demo_if_empty()


def _seed_demo_if_empty():
    from .database import SessionLocal
    from .models import User

    db = SessionLocal()
    try:
        empty = db.query(User).count() == 0
    finally:
        db.close()
    if empty:
        from .jobs import seed_demo
        seed_demo.main()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


# --- hosted single-service mode ----------------------------------------------
# When STATIC_DIR points at the built frontend, this app serves it too: real
# files (JS, CSS, icons, service worker) directly, and index.html for every
# other non-API path so client-side routes like /passport/<token> work when
# opened straight from a QR code.
_static = Path(settings.STATIC_DIR).resolve() if settings.STATIC_DIR else None

if _static and (_static / "index.html").is_file():

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (_static / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_static):
            return FileResponse(candidate)
        # index.html must never be cached, or clients miss new deploys.
        return FileResponse(_static / "index.html", headers={"Cache-Control": "no-cache"})

else:

    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "message": "GreenThread API",
            "version": "1.0.0",
            "docs": "/docs"
        }
