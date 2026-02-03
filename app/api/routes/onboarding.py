"""API routes for onboarding flow."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.onboarding import OnboardingService
from app.schemas.onboarding import (
    OnboardingStatusResponse,
    OnboardingAnswers,
    OnboardingProgressUpdate,
    OnboardingSubmitResponse,
)
from app.api.routes.dependencies import get_current_user_id


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get onboarding completion status for current user."""
    try:
        service = OnboardingService(db)
        status = await service.get_onboarding_status(user_id)
        return OnboardingStatusResponse(**status)
    except Exception as e:
        logger.error(f"Error getting onboarding status for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get onboarding status")


@router.post("/submit", response_model=OnboardingSubmitResponse, status_code=200)
async def submit_onboarding(
    answers: OnboardingAnswers,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Submit complete onboarding answers.
    
    This endpoint:
    - Validates all answers
    - Maps answers to appropriate user_* tables
    - Stores audit trail in onboarding_responses
    - Marks user as having completed onboarding
    """
    try:
        service = OnboardingService(db)
        profile = await service.submit_onboarding(user_id, answers, version="v1")
        
        return OnboardingSubmitResponse(
            message="Onboarding completed successfully!",
            completed_at=profile.onboarding_completed_at,
            version=profile.onboarding_version
        )
    except ValueError as e:
        logger.warning(f"Validation error in onboarding submission: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting onboarding for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit onboarding")


@router.patch("/progress", status_code=200)
async def save_onboarding_progress(
    progress: OnboardingProgressUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Save partial onboarding progress.
    
    This is useful for:
    - Analytics (track completion rates, drop-off points)
    - Recovery if user abandons and returns
    """
    try:
        service = OnboardingService(db)
        await service.save_progress(
            user_id,
            progress.question_id,
            progress.answer_value,
            progress.question_set_version
        )
        return {"message": "Progress saved"}
    except Exception as e:
        logger.error(f"Error saving onboarding progress for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save progress")