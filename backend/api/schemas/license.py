from datetime import datetime
from pydantic import BaseModel


class LicenseRead(BaseModel):
    id:                  int
    key:                 str
    note:                str | None
    activated_by_email:  str | None
    activated_by_name:   str | None
    is_active:           bool
    is_valid:            bool
    expires_at:          datetime | None
    created_at:          datetime
    activated_at:        datetime | None

    model_config = {"from_attributes": True}


class LicenseCreate(BaseModel):
    note:       str | None = None
    expires_at: datetime | None = None   # None = бессрочно


class LicenseActivate(BaseModel):
    key:   str
    email: str
    name:  str | None = None


class LicenseVerifyResult(BaseModel):
    valid:   bool
    message: str
