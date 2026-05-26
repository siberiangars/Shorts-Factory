from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from models.generation_log import LogStatus


class GenerationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    step_name: str
    status: LogStatus
    duration_ms: int | None
    cost_usd: Decimal | None
    payload_json: dict | None
    created_at: datetime
