
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GameResultPlayerScore(BaseModel):
    player_id: int
    display_name: str
    score: int


class GameResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    winner_player_id: int | None = None
    final_scores: list[GameResultPlayerScore]
    completed_at: datetime


class GameHistoryItem(BaseModel):
    room_code: str
    status: str
    current_round: int
    total_rounds: int
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    result: GameResultResponse | None = None
