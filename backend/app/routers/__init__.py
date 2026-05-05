# Routers module
from app.routers.auth import router as auth_router
from app.routers.documents import router as documents_router
from app.routers.decision_flow import router as decision_flow_router
from app.routers.knowledge_graph import router as knowledge_graph_router

try:
    from app.routers.ontology import router as ontology_router
except ImportError:
    ontology_router = None

try:
    from app.routers.aip import router as aip_router
except ImportError:
    aip_router = None

__all__ = [
    "auth_router",
    "documents_router",
    "decision_flow_router",
    "knowledge_graph_router",
    "ontology_router",
    "aip_router",
]