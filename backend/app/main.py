from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .routes import auth, factory, production, carbon, water_energy, chemicals, reports, dashboard, audit, ocr, verify

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


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "GreenThread API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
