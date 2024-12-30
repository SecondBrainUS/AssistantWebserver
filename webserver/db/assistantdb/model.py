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
    picture = Column(String, nullable=True)
    name = Column(String, nullable=True)
    created = Column(DateTime, default=func.now())
    updated = Column(DateTime, default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "email": self.email,
            "auth_type": self.auth_type,
            "picture": self.picture,
            "name": self.name,
            "created": self.created,
            "updated": self.updated,
        }

class AuthGoogle(Base):
    __tablename__ = "auth_google"
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), primary_key=True)
    google_user_id = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    token_expiry = Column(String, nullable=True)
    created = Column(DateTime, default=func.now())
    updated = Column(DateTime, default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "google_user_id": self.google_user_id,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expiry": self.token_expiry,
            "created": self.created,
            "updated": self.updated,
        }

class UserSession(Base):
    __tablename__ = "user_sessions"
    session_id = Column(String, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    access_token_expires = Column(DateTime, nullable=False)
    refresh_token_expires = Column(DateTime, nullable=False)
    session_expires = Column(DateTime, nullable=False)
    created = Column(DateTime, default=func.now())
    updated = Column(DateTime, default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "session_expires": self.session_expires,
            "access_token_expires": self.access_token_expires,
            "refresh_token_expires": self.refresh_token_expires,
            "created": self.created,
            "updated": self.updated,
        }