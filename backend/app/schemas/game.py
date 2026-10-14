
from datetime import datetime

from pydantic import BaseModel


class RoundResponse(BaseModel):
    id: int
    room_code: str
    round_number: int
    drawer_player_id: int
    started_at: datetime
    ended_at: datetime | None = None


class DrawerRoundResponse(RoundResponse):
    word: str


class RoundAdvanceResponse(BaseModel):
    room_code: str
    status: str
    current_round: int
    total_rounds: int
    message: str
