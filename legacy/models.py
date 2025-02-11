from sqlalchemy import Column, String, JSON, DateTime, func
from database import Base
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# class ModerationResult(Base):
#     __tablename__ = "moderation_results"

#     text_id = Column(String, primary_key=True, index=True)
#     text = Column(String, nullable=False)
#     result = Column(JSON, nullable=False)
#     created_at = Column(DateTime, server_default=func.now())

class ModerationResult(Base):
    __tablename__ = "moderation_results"

    text_id = Column(String, primary_key=True, index=True)
    text = Column(String, nullable=False)
    result = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, server_default=func.now())
