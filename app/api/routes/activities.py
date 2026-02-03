from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.program import ActivityDefinition, ActivityInstance
from app.models.enums import ActivitySource
from app.schemas.logging import ActivityInstanceCreate
from app.config.settings import get_settings
from app.api.routes.dependencies import get_current_user_id

router = APIRouter()
settings = get_settings()

@router.get("/definitions")
async def get_activity_definitions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ActivityDefinition))
    return result.scalars().all()

@router.post("/log")
async def log_activity(
    activity: ActivityInstanceCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    instance = ActivityInstance(
        user_id=user_id,
        activity_definition_id=activity.activity_definition_id,
        name=activity.activity_name,
        duration_seconds=activity.duration_minutes * 60,
        distance_km=activity.distance_km,
        notes=activity.notes,
        perceived_difficulty=activity.perceived_difficulty,
        enjoyment_rating=activity.enjoyment_rating,
        performed_start=activity.performed_start,
        source=ActivitySource.MANUAL
    )
    db.add(instance)
    await db.commit()
    return {"id": instance.id, "status": "logged"}
