from decimal import Decimal

from pydantic import BaseModel


class StatsRead(BaseModel):
    pending: int
    in_progress: int
    done_today: int
    done_total: int
    avg_cost_usd: Decimal | None
