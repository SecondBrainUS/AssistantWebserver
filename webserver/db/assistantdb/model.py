from sqlalchemy import Column, String, ForeignKey, DateTime, Double
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    auth_type = Column(String, nullable=False)  # ex: "google", "microsoft"
    created = Column(DateTime, default=func.now())
    updated = Column(DateTime, default=func.now(), onupdate=func.now())

class AuthGoogle(Base):
    __tablename__ = "auth_google"
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), primary_key=True)
    google_user_id = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    token_expiry = Column(String, nullable=True)
    created = Column(DateTime, default=func.now())
    updated = Column(DateTime, default=func.now(), onupdate=func.now())
