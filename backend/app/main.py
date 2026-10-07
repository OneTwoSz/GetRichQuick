from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
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

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER = "x-requested-with"


@app.middleware("http")
async def csrf_and_security_headers(request: Request, call_next):
    """CSRF guard + baseline security headers.

    State-changing /api requests must carry X-Requested-With. Browsers only
    allow cross-origin pages to send custom headers after a CORS preflight,
    which this server only grants to the origins below — so another site
    can't make a signed-in user's browser submit requests (the session
    cookie is also SameSite=Lax)."""
    if (request.method in _UNSAFE_METHODS and request.url.path.startswith("/api/")
            and CSRF_HEADER not in request.headers):
        return JSONResponse(status_code=403, content={"detail": "Missing X-Requested-With header"})
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


# CORS middleware - allow the dev frontend to access the API. Hosted deploys
# serve the frontend from the same origin, so no CORS is needed there.
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
        # In a worker thread: the seed is synchronous and runs its own event
        # loop for report generation, which can't nest inside this one.
        await run_in_threadpool(_seed_demo_if_empty)


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

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
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
