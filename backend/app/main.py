from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from datetime import datetime

from app.core.config import settings
from app.routers import auth, documents, decision_flow, knowledge_graph
from app.services import neo4j_client, postgres_client, rabbitmq_client, minio_client, redis_client
from sqlalchemy import text

# Rate limiting (slowapi)
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Prometheus metrics
from prometheus_fastapi_instrumentator import Instrumentator

# OpenTelemetry
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

# Structured logging
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = structlog.get_logger(__name__)

# Initialize OpenTelemetry Tracer
try:
    otlp_exporter = OTLPSpanExporter(endpoint="http://otel-collector:4317", insecure=True)
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace.set_tracer_provider(TracerProvider())
    trace.get_tracer_provider().add_span_processor(span_processor)
except Exception as e:
    logger.warning(f"OpenTelemetry tracer init failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Knowledge Decision Platform...")
    
    # Initialize connections (with error handling for degraded mode)
    try:
        await postgres_client.connect()
        logger.info("PostgreSQL connected")
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed: {e}")
    
    try:
        await neo4j_client.connect()
        logger.info("Neo4j connected")
    except Exception as e:
        logger.warning(f"Neo4j connection failed: {e}")
    
    try:
        await rabbitmq_client.connect()
        logger.info("RabbitMQ connected")
    except Exception as e:
        logger.warning(f"RabbitMQ connection failed: {e}")
    
    try:
        await minio_client.initialize()
        logger.info("MinIO initialized")
    except Exception as e:
        logger.warning(f"MinIO initialization failed: {e}")
    
    try:
        await redis_client.connect()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
    
    logger.info("Application startup complete (degraded mode if services unavailable)")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Knowledge Decision Platform...")
    try:
        await neo4j_client.close()
    except Exception:
        pass
    try:
        await rabbitmq_client.close()
    except Exception:
        pass
    try:
        await redis_client.close()
    except Exception:
        pass
    try:
        await postgres_client.close()
    except Exception:
        pass
    logger.info("Shutdown complete")


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise Knowledge Decision Platform - Open Source Alternative to Palantir",
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda req, exc: JSONResponse(
    status_code=429,
    content={"detail": "Rate limit exceeded. Please try again later."}
))

# Prometheus instrumentation
Instrumentator().instrument(app).expose(app)

# OpenTelemetry instrumentation
FastAPIInstrumentor.instrument_app(app)
try:
    SQLAlchemyInstrumentor().instrument()
except Exception as e:
    logger.warning(f"SQLAlchemy instrumentation failed: {e}")
try:
    RedisInstrumentor().instrument()
except Exception as e:
    logger.warning(f"Redis instrumentation failed: {e}")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix=settings.API_PREFIX, tags=["Authentication"])
app.include_router(documents.router, prefix=f"{settings.API_PREFIX}/documents", tags=["Documents"])
app.include_router(decision_flow.router, prefix=f"{settings.API_PREFIX}/decision-flows", tags=["Decision Flows"])
app.include_router(knowledge_graph.router, prefix=f"{settings.API_PREFIX}/knowledge-graph", tags=["Knowledge Graph"])

# NEW: Ontology and AIP routers (imported with lazy handling for missing deps)
try:
    from app.routers import ontology
    app.include_router(ontology.router, prefix=f"{settings.API_PREFIX}/ontology", tags=["Ontology"])
    logger.info("Ontology router registered")
except Exception as e:
    logger.warning(f"Ontology router not available: {e}")

try:
    from app.routers import aip
    app.include_router(aip.router, prefix=f"{settings.API_PREFIX}/aip", tags=["AIP"])
    logger.info("AIP router registered")
except Exception as e:
    logger.warning(f"AIP router not available: {e}")


@app.get("/")
@limiter.limit("60/minute")
async def root(request: Request):
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
@limiter.limit("30/minute")
async def health_check(request: Request):
    """Health check endpoint with actual service connectivity checks"""
    services_status = {}
    overall_healthy = True
    
    # Check PostgreSQL
    try:
        if postgres_client.connected and postgres_client.engine:
            async with postgres_client.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            services_status["postgres"] = {"status": "healthy", "uri": settings.POSTGRES_HOST}
        else:
            services_status["postgres"] = {"status": "unhealthy", "error": "Not connected"}
            overall_healthy = False
    except Exception as e:
        services_status["postgres"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    # Check Neo4j
    try:
        if neo4j_client.connected:
            services_status["neo4j"] = {"status": "healthy", "uri": settings.NEO4J_URI}
        else:
            services_status["neo4j"] = {"status": "unhealthy", "error": "Not connected"}
            overall_healthy = False
    except Exception as e:
        services_status["neo4j"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    # Check RabbitMQ
    try:
        if rabbitmq_client.connected:
            services_status["rabbitmq"] = {"status": "healthy", "uri": settings.RABBITMQ_HOST}
        else:
            services_status["rabbitmq"] = {"status": "unhealthy", "error": "Not connected"}
            overall_healthy = False
    except Exception as e:
        services_status["rabbitmq"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    # Check MinIO
    try:
        if minio_client.client:
            services_status["minio"] = {"status": "healthy", "endpoint": settings.MINIO_ENDPOINT}
        else:
            services_status["minio"] = {"status": "unhealthy", "error": "Not initialized"}
            overall_healthy = False
    except Exception as e:
        services_status["minio"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    return {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.APP_VERSION,
        "services": services_status
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
