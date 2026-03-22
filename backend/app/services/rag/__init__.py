"""RAG 检索变体与调度。参照 IMPLEMENTATION_PLAN Phase 3。"""

from app.services.rag.context import assemble_context
from app.services.rag.dispatcher import dispatch_retrieve, get_active_rag_config, get_rag_config_by_id

__all__ = [
    "assemble_context",
    "dispatch_retrieve",
    "get_active_rag_config",
    "get_rag_config_by_id",
]
