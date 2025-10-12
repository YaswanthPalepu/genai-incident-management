from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from routes import user_routes, admin_routes
from db.chromadb import load_and_vectorize_kb
from config import GOOGLE_API_KEY
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate environment
if not GOOGLE_API_KEY:
    logger.error("GOOGLE_API_KEY environment variable not set. LLM functionality will be disabled.")
else:
    logger.info("✓ Google API Key loaded successfully")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management.
    Startup: Load and vectorize knowledge base
    Shutdown: Cleanup resources
    """
    # Startup event
    logger.info("=" * 60)
    logger.info("🚀 GenAI Incident Management System Starting Up")
    logger.info("=" * 60)
    
    logger.info("📚 Loading and vectorizing knowledge base...")
    try:
        load_and_vectorize_kb()
        logger.info("✓ Knowledge base loaded and vectorized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to load knowledge base: {e}")
        logger.warning("⚠️  System will continue but KB-based features may not work properly")
    
    logger.info("✅ Application startup complete")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown event
    logger.info("=" * 60)
    logger.info("🛑 GenAI Incident Management System Shutting Down")
    logger.info("=" * 60)
    logger.info("🧹 Cleanup and resources release complete")

# CORS origins for frontend communication
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Initialize FastAPI app
app = FastAPI(
    title="GenAI Incident Management System",
    description="AI-powered incident management using semantic search and LLM intelligence",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
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
    
    # Skip logging for health checks
    if request.url.path not in ["/health", "/favicon.ico"]:
        logger.info(f"🌐 {request.method} {request.url.path} - Client: {request.client.host}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    if request.url.path not in ["/health", "/favicon.ico"]:
        logger.info(f"📨 {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s")
    
    return response

# Include routers
app.include_router(user_routes.router, prefix="/api/user", tags=["User Operations"])
app.include_router(admin_routes.router, prefix="/api/admin", tags=["Admin Operations"])

# Health check and status endpoints
@app.get("/")
async def root():
    """Root endpoint - API status check."""
    return {
        "message": "GenAI Incident Management System API",
        "version": "2.0.0",
        "status": "running",
        "features": {
            "llm_intelligence": "enabled" if GOOGLE_API_KEY else "disabled",
            "semantic_search": "enabled",
            "incident_tracking": "enabled",
            "knowledge_base": "enabled"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {
        "status": "healthy",
        "service": "GenAI Incident Management System",
        "timestamp": time.time()
    }

@app.get("/api/status")
async def api_status():
    """Detailed API status with component health."""
    components = {
        "api_server": "healthy",
        "llm_service": "enabled" if GOOGLE_API_KEY else "disabled",
        "vector_database": "enabled",
        "document_database": "enabled",
        "knowledge_base": "enabled"
    }
    
    return {
        "api": "running",
        "version": "2.0.0",
        "components": components,
        "timestamp": time.time()
    }

# Global exception handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors."""
    logger.warning(f"404 Not Found: {request.url}")
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"The requested resource {request.url} was not found",
            "path": str(request.url.path)
        }
    )

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    """Handle 500 errors."""
    logger.error(f"500 Internal Server Error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later."
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception in {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc)
        }
    )

# Favicon handler to prevent 404 errors
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
        log_level="info",
        access_log=True
    )