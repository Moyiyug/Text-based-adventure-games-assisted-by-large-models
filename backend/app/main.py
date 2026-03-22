from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin.metadata import router as admin_metadata_router
from app.api.admin.rag_configs import router as admin_rag_configs_router
from app.api.admin.stories import router as admin_stories_router
from app.api.auth import router as auth_router
from app.api.stories import router as stories_router
from app.api.users import router as users_router
from app.core.config import settings

app = FastAPI(
    title="RAG Interactive Narrative",
    description="交互式文字叙事冒险平台",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(admin_stories_router, prefix="/api/admin/stories", tags=["admin-stories"])
app.include_router(admin_metadata_router, prefix="/api/admin/stories", tags=["admin-metadata"])
app.include_router(admin_rag_configs_router, prefix="/api/admin", tags=["admin-rag-configs"])
app.include_router(stories_router, prefix="/api/stories", tags=["stories"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
