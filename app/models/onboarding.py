"""Onboarding models for tracking user onboarding progress and responses."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Index
from sqlalchemy.orm import relationship

from app.db.database import Base


class OnboardingResponse(Base):
    """Stores user's onboarding question answers for analytics and audit trail."""
    __tablename__ = "onboarding_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    question_id = Column(String(100), nullable=False, index=True)
    answer_value = Column(JSON, nullable=True)
    answered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    question_set_version = Column(String(50), nullable=False, default="v1")
    
    # Relationships
    user = relationship("User")

    __table_args__ = (
        Index("idx_onboarding_user_version", "user_id", "question_set_version"),
    )

    def __repr__(self):
        return f"<OnboardingResponse(user_id={self.user_id}, question_id='{self.question_id}')>"
