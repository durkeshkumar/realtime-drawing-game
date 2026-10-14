
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_player_in_room
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.game_result import GameResult
from app.models.game_room import GameRoom
from app.models.game_round import GameRound
from app.models.guess import Guess
from app.models.player import Player
from app.schemas.game_result import (
    GameHistoryItem,
    GameResultPlayerScore,
    GameResultResponse,
)

router = APIRouter(tags=["Game Results"])


def get_room_or_404(db: Session, room_code: str) -> GameRoom:
    room = (
        db.query(GameRoom)
        .filter(GameRoom.room_code == room_code.strip().upper())
        .first()
    )

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found.",
        )

    return room


def serialize_result(result: GameResult) -> GameResultResponse:
    return GameResultResponse(
        id=result.id,
        room_id=result.room_id,
        winner_player_id=result.winner_player_id,
        final_scores=[
            GameResultPlayerScore.model_validate(score)
            for score in result.final_scores
        ],
        completed_at=result.completed_at,
    )


@router.get(
    "/rooms/{room_code}/results",
    response_model=GameResultResponse,
)
@limiter.limit("30/minute")
def get_game_result(
    request: Request,
    room_code: str,
    current_player: Player = Depends(get_current_player_in_room),
    db: Session = Depends(get_db),
):
    room = get_room_or_404(db, room_code)

    if current_player.room_id != room.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this room.",
        )

    if room.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The game has not completed yet.",
        )

    result = (
        db.query(GameResult)
        .filter(GameResult.room_id == room.id)
        .first()
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The saved result is not available.",
        )

    return serialize_result(result)


@router.get(
    "/rooms/{room_code}/history",
    response_model=GameHistoryItem,
)
@limiter.limit("30/minute")
def get_room_history(
    request: Request,
    room_code: str,
    current_player: Player = Depends(get_current_player_in_room),
    db: Session = Depends(get_db),
):
    room = get_room_or_404(db, room_code)

    if current_player.room_id != room.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this room.",
        )

    result = (
        db.query(GameResult)
        .filter(GameResult.room_id == room.id)
        .first()
    )

    return GameHistoryItem(
        room_code=room.room_code,
        status=room.status,
        current_round=room.current_round,
        total_rounds=room.total_rounds,
        created_at=room.created_at,
        started_at=room.started_at,
        ended_at=room.ended_at,
        result=serialize_result(result) if result else None,
    )


@router.get("/rooms/{room_code}/rounds/{round_number}/guesses")
@limiter.limit("30/minute")
def get_round_guesses(
    request: Request,
    room_code: str,
    round_number: int,
    current_player: Player = Depends(get_current_player_in_room),
    db: Session = Depends(get_db),
):
    room = get_room_or_404(db, room_code)

    if current_player.room_id != room.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this room.",
        )

    if round_number < 1 or round_number > room.total_rounds:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Round number is outside the valid range.",
        )

    game_round = (
        db.query(GameRound)
        .filter(
            GameRound.room_id == room.id,
            GameRound.round_number == round_number,
        )
        .first()
    )

    if game_round is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Round not found.",
        )

    if game_round.ended_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Guess history is available after the round ends.",
        )

    guesses = (
        db.query(Guess, Player)
        .join(Player, Guess.player_id == Player.id)
        .filter(Guess.round_id == game_round.id)
        .order_by(Guess.submitted_at.asc())
        .all()
    )

    return {
        "room_code": room.room_code,
        "round_number": game_round.round_number,
        "drawer_player_id": game_round.drawer_player_id,
        "guesses": [
            {
                "player_id": player.id,
                "display_name": player.display_name,
                "guess": guess.guess_text,
                "is_correct": guess.is_correct,
                "submitted_at": guess.submitted_at,
            }
            for guess, player in guesses
        ],
    }


@router.get("/history")
@limiter.limit("30/minute")
def get_completed_game_history(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    results = (
        db.query(GameResult, GameRoom)
        .join(GameRoom, GameResult.room_id == GameRoom.id)
        .order_by(GameResult.completed_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "room_code": room.room_code,
                "status": room.status,
                "current_round": room.current_round,
                "total_rounds": room.total_rounds,
                "created_at": room.created_at,
                "started_at": room.started_at,
                "ended_at": room.ended_at,
                "result": serialize_result(result),
            }
            for result, room in results
        ],
        "limit": limit,
        "offset": offset,
    }
