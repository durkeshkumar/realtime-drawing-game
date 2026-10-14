
import random
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.game_room import GameRoom
from app.models.game_round import GameRound
from app.models.player import Player


WORDS = [
    "apple",
    "airplane",
    "bicycle",
    "butterfly",
    "camera",
    "candle",
    "castle",
    "cat",
    "cloud",
    "computer",
    "dolphin",
    "elephant",
    "football",
    "guitar",
    "hamburger",
    "helicopter",
    "ice cream",
    "jellyfish",
    "mountain",
    "octopus",
    "penguin",
    "rainbow",
    "rocket",
    "sandwich",
    "snowman",
    "sunflower",
    "telescope",
    "turtle",
    "umbrella",
    "watermelon",
]


def get_active_players(
    db: Session,
    room_id: int,
) -> list[Player]:
    return (
        db.query(Player)
        .filter(
            Player.room_id == room_id,
            Player.left_at.is_(None),
        )
        .order_by(Player.joined_at.asc(), Player.id.asc())
        .all()
    )


def start_round(
    db: Session,
    room: GameRoom,
) -> GameRound:
    if room.status != "playing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The game must be playing to start a round.",
        )

    if room.current_round < 1 or room.current_round > room.total_rounds:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The current round number is invalid.",
        )

    existing_round = (
        db.query(GameRound)
        .filter(
            GameRound.room_id == room.id,
            GameRound.round_number == room.current_round,
        )
        .first()
    )

    if existing_round is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The current round has already been initialized.",
        )

    players = get_active_players(db, room.id)

    if len(players) < settings.MIN_PLAYERS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"At least {settings.MIN_PLAYERS} active players "
                "are required to start a round."
            ),
        )

    # Rotate drawers in join order instead of choosing randomly.
    drawer_index = (room.current_round - 1) % len(players)
    drawer = players[drawer_index]

    game_round = GameRound(
        room_id=room.id,
        round_number=room.current_round,
        drawer_player_id=drawer.id,
        word=random.choice(WORDS),
        started_at=datetime.utcnow(),
    )

    try:
        db.add(game_round)
        db.commit()
        db.refresh(game_round)
        return game_round
    except Exception:
        db.rollback()
        raise


def finish_round(
    db: Session,
    room: GameRoom,
) -> GameRound:
    if room.status != "playing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The game is not currently playing.",
        )

    game_round = (
        db.query(GameRound)
        .filter(
            GameRound.room_id == room.id,
            GameRound.round_number == room.current_round,
        )
        .with_for_update()
        .first()
    )

    if game_round is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The current round has not been initialized.",
        )

    if game_round.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The current round has already ended.",
        )

    try:
        game_round.ended_at = datetime.utcnow()

        if room.current_round >= room.total_rounds:
            room.status = "completed"
            room.ended_at = datetime.utcnow()
        else:
            room.current_round += 1

        db.commit()
        db.refresh(game_round)
        db.refresh(room)

        return game_round
    except Exception:
        db.rollback()
        raise
