
from sqlalchemy.orm import Session

from app.models.game_result import GameResult
from app.models.game_room import GameRoom
from app.models.player import Player


def save_game_result(
    db: Session,
    room: GameRoom,
) -> GameResult | None:
    """Persist the final scores and winner for a completed game."""

    if room.status != "completed":
        return None

    # Make this operation safe to call more than once.
    existing_result = (
        db.query(GameResult)
        .filter(GameResult.room_id == room.id)
        .first()
    )

    if existing_result is not None:
        return existing_result

    players = (
        db.query(Player)
        .filter(Player.room_id == room.id)
        .order_by(Player.score.desc(), Player.joined_at.asc())
        .all()
    )

    final_scores = [
        {
            "player_id": player.id,
            "display_name": player.display_name,
            "score": player.score,
        }
        for player in players
    ]

    winner_player_id = players[0].id if players else None

    result = GameResult(
        room_id=room.id,
        winner_player_id=winner_player_id,
        final_scores=final_scores,
    )

    db.add(result)
    db.commit()
    db.refresh(result)

    return result
