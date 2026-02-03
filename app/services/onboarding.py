"""Service for handling onboarding data submission and mapping to user tables."""
from datetime import datetime
from typing import Any

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EnjoyableActivity, Sex
from app.models.onboarding import OnboardingResponse
from app.models.user import User, UserProfile, UserEnjoyableActivity
from app.schemas.onboarding import OnboardingAnswers


class OnboardingService:
    """Service for processing onboarding answers."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def submit_onboarding(self, user_id: int, answers: OnboardingAnswers, version: str = "v1") -> UserProfile:
        """
        Submit complete onboarding answers.
        
        Maps answers to appropriate user_* tables:
        - users: name
        - user_profiles: date_of_birth, sex, goals, equipment_familiarity, athletic_background, gym_comfort_level
        - user_enjoyable_activities: activities from athletic_background
        - user_movement_rules: based on movement_experience (optional, for future)
        
        Returns updated UserProfile.
        """
        
        try:
            # 1. Fetch user and profile
            user = await self.db.get(User, user_id)
            if not user:
                raise ValueError(f"User not found: {user_id}")
            
            profile = await self.db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
            if not profile:
                profile = UserProfile(user_id=user_id)
                self.db.add(profile)
            
            # 2. Update basic user info (name is optional since provided during registration)
            # Only update if name is provided in onboarding (backward compatibility)
            if answers.name:
                user.name = answers.name
            
            # 3. Update profile basics
            if answers.date_of_birth:
                from datetime import datetime as dt
                try:
                    profile.date_of_birth = dt.fromisoformat(answers.date_of_birth).date()
                except ValueError:
                    pass  # Keep existing or leave as None
            
            if answers.sex:
                try:
                    profile.sex = Sex(answers.sex.upper())
                except ValueError:
                    pass  # Invalid enum, skip
            
            # 4. Update onboarding-specific fields
            if answers.gym_comfort_level:
                profile.gym_comfort_level = answers.gym_comfort_level
            
            if answers.equipment_familiarity:
                profile.equipment_familiarity = answers.equipment_familiarity
            
            if answers.athletic_background:
                profile.athletic_background = answers.athletic_background
            
            # 5. Update goals
            if answers.goal_category:
                profile.long_term_goal_category = answers.goal_category
            
            if answers.goal_description:
                profile.long_term_goal_description = answers.goal_description
            
            # 6. Update enjoyable activities
            if answers.enjoyable_activities:
                # Delete existing activities
                await self.db.execute(
                    delete(UserEnjoyableActivity).where(UserEnjoyableActivity.user_id == user_id)
                )
                
                # Add new activities
                for activity_type in answers.enjoyable_activities:
                    try:
                        activity_enum = EnjoyableActivity(activity_type.upper())
                        new_activity = UserEnjoyableActivity(
                            user_id=user_id,
                            activity_type=activity_enum,
                            recommend_every_days=28
                        )
                        self.db.add(new_activity)
                    except ValueError:
                        # Invalid enum, skip
                        pass
            
            # 7. Update movement experience (map to movement rules if desired)
            # For MVP, we store this as JSON in profile for future use
            # In future, we could map specific movements to UserMovementRule
            if answers.movement_experience:
                # Store in profile for future processing
                if profile.athletic_background is None:
                    profile.athletic_background = {}
                profile.athletic_background['movement_experience'] = answers.movement_experience
            
            # 8. Mark onboarding as complete
            profile.onboarding_completed_at = datetime.utcnow()
            profile.onboarding_version = version
            
            # 9. Store audit responses
            await self._store_audit_responses(user_id, answers, version)
            
            # 10. Commit all changes
            await self.db.commit()
            await self.db.refresh(profile)
            
            return profile
            
        except Exception as e:
            await self.db.rollback()
            raise e
    
    async def _store_audit_responses(self, user_id: int, answers: OnboardingAnswers, version: str):
        """Store individual answers in onboarding_responses for analytics."""
        
        response_map = {
            'name': answers.name,
            'date_of_birth': answers.date_of_birth,
            'sex': answers.sex,
            'gym_comfort_level': answers.gym_comfort_level,
            'athletic_background': answers.athletic_background,
            'equipment_familiarity': answers.equipment_familiarity,
            'movement_experience': answers.movement_experience,
            'enjoyable_activities': answers.enjoyable_activities,
            'goal_category': answers.goal_category,
            'goal_description': answers.goal_description,
        }
        
        for question_id, answer_value in response_map.items():
            if answer_value is not None:
                response = OnboardingResponse(
                    user_id=user_id,
                    question_id=question_id,
                    answer_value=answer_value,
                    question_set_version=version
                )
                self.db.add(response)
    
    async def get_onboarding_status(self, user_id: int) -> dict:
        """Get onboarding status for a user."""
        
        profile = await self.db.scalar(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        
        if not profile or profile.onboarding_completed_at is None:
            return {
                'completed': False,
                'version': None
            }
        
        return {
            'completed': True,
            'version': profile.onboarding_version
        }
    
    async def save_progress(self, user_id: int, question_id: str, answer_value: Any, version: str = "v1"):
        """Save partial onboarding progress."""
        
        response = OnboardingResponse(
            user_id=user_id,
            question_id=question_id,
            answer_value=answer_value,
            question_set_version=version
        )
        self.db.add(response)
        await self.db.commit()