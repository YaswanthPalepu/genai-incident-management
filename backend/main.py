# backend/main.py - REFACTORED
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from routes import user_routes, admin_routes
from db.chromadb import load_and_vectorize_kb
from config import GOOGLE_API_KEY, CORS_ORIGINS
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate environment
if not GOOGLE_API_KEY:
    logger.error("GOOGLE_API_KEY environment variable not set!")
else:
    logger.info("✓ Google API Key loaded")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # Startup
    logger.info("=" * 60)
    logger.info("🚀 GenAI Incident Management System Starting")
    logger.info("=" * 60)
    
    logger.info("📚 Loading and vectorizing knowledge base...")
    try:
        load_and_vectorize_kb()
        logger.info("✓ KB loaded and vectorized")
    except Exception as e:
        logger.error(f"✗ Failed to load KB: {e}")
        logger.warning("⚠️  System continuing without KB")
    
    logger.info("✅ Startup complete")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("🛑 GenAI Incident Management System Shutting Down")
    logger.info("=" * 60)

# Initialize FastAPI app
app = FastAPI(
    title="GenAI Incident Management System",
    description="AI-powered incident management with semantic KB search",
    version="3.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    if request.url.path not in ["/health", "/favicon.ico", "/docs", "/redoc"]:
        logger.info(f"🌐 {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    if request.url.path not in ["/health", "/favicon.ico", "/docs", "/redoc"]:
        logger.info(f"📨 {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
    
    return response

# Include routers
app.include_router(user_routes.router, prefix="/api/user", tags=["User"])
app.include_router(admin_routes.router, prefix="/api/admin", tags=["Admin"])

# Health endpoints
@app.get("/")
async def root():
    """Root endpoint - API status"""
    return {
        "message": "GenAI Incident Management System API",
        "version": "3.0.0",
        "status": "running",
        "features": {
            "llm_intelligence": "enabled" if GOOGLE_API_KEY else "disabled",
            "hybrid_search": "enabled",
            "incident_tracking": "enabled"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "GenAI Incident Management System",
        "timestamp": time.time()
    }

@app.get("/api/status")
async def api_status():
    """Detailed API status"""
    return {
        "api": "running",
        "version": "3.0.0",
        "components": {
            "api_server": "healthy",
            "llm_service": "enabled" if GOOGLE_API_KEY else "disabled",
            "vector_database": "enabled",
            "document_database": "enabled"
        },
        "timestamp": time.time()
    }

# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    logger.warning(f"404 Not Found: {request.url}")
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"Resource not found: {request.url.path}",
            "path": str(request.url.path)
        }
    )

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    logger.error(f"500 Internal Server Error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc)
        }
    )

@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(content={"status": "no favicon"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )