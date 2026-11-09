from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .routes.sessions import router as sessions_router
from .routes.questions import router as questions_router
from .routes.answers import router as answers_router
from .routes.audio import router as audio_router

app = FastAPI(
    title="RoleReady Backend & Scoring Engine",
    description="Backend API and Prometheus 7B scoring core for AI interview preparation.",
    version="1.0.0",
)

# CORS Middleware (Frontend integration for Khaled)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"An unexpected error occurred: {str(exc)}"},
    )

# Health Check
@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "RoleReady Backend",
        "database_backend": settings.DATABASE_BACKEND,
        "scorer_backend": settings.SCORER_BACKEND,
        "version": "1.0.0",
    }

# Register API Routers
app.include_router(sessions_router)
app.include_router(questions_router)
app.include_router(answers_router)
app.include_router(audio_router)
