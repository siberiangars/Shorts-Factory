from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func
from models.base import Base


class License(Base):
    __tablename__ = "licenses"

    id         = Column(Integer, primary_key=True, index=True)
    key        = Column(String(32), unique=True, nullable=False, index=True)
    note       = Column(String(255), nullable=True)   # заметка admin-а (кому выдан)

    # Кто активировал
    activated_by_email = Column(String(255), nullable=True, index=True)
    activated_by_name  = Column(String(255), nullable=True)

    is_active  = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # None = бессрочно

    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    activated_at  = Column(DateTime(timezone=True), nullable=True)

    @property
    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < datetime.now(timezone.utc):
            return False
        return True
