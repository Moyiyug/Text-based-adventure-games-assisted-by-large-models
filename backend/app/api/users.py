from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.user import UpdateSettingsRequest

router = APIRouter()


@router.put("/me/settings", response_model=UserResponse)
async def update_settings(
    data: UpdateSettingsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.bio is not None:
        user.bio = data.bio
    await db.flush()
    await db.refresh(user)
    return user
