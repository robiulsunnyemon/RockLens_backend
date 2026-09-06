import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.core.database import init_db
from app.api.v1.api import api_router

logger = logging.getLogger("rocklens_backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables if not already created
    try:
        await init_db()
    except Exception as e:
        logger.warning(f"Note: DB auto-init notice: {e}")
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware (Enable for Flutter Mobile, Web, and Desktop)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": str(request.url.path),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        errors.append({"field": field, "message": msg})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "detail": "Request payload validation failed.",
            "errors": errors,
            "path": str(request.url.path),
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Database error at {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "detail": "A database transaction error occurred while processing your request.",
            "path": str(request.url.path),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server exception at {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "detail": "Internal server error occurred.",
            "path": str(request.url.path),
        },
    )


from app.api.v1.endpoints.identification import router as identification_router

# Include API V1 Router (/api/v1/...)
app.include_router(api_router, prefix=settings.API_V1_STR)

# Also support direct /specimens/identify for mobile clients
app.include_router(identification_router)



@app.get("/", include_in_schema=False)
async def root():
    """Root redirect to interactive Swagger API documentation."""
    return RedirectResponse(url="/docs")


@app.get("/api/v1/docs", include_in_schema=False)
async def v1_docs_redirect():
    """Redirect /api/v1/docs to standard /docs."""
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "system": "RockLens Geological Intelligence API",
        "version": "3.0.0",
        "docs": "/docs",
    }
