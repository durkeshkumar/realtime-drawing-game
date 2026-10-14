from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_player_in_room
from app.core.limiter import limiter
from app.db.session import get_db
from app.game.result_service import save_game_result
from app.game.round_service import (
    finish_round,
    get_active_players,
    start_round,
)
from app.game.round_timer import (
    cancel_round_timer,
    start_round_timer,
)
from app.game.websocket_manager import manager
from app.models.game_round import GameRound
from app.models.game_room import GameRoom
from app.models.player import Player
from app.schemas.game import (
    DrawerRoundResponse,
    RoundAdvanceResponse,
    RoundResponse,
)

router = APIRouter(tags=["Game"])


class PlayerScoreResponse(BaseModel):
    player_id: int
    display_name: str
    score: int
    is_ready: bool


class ScoreboardResponse(BaseModel):
    room_code: str
    status: str
    current_round: int
    total_rounds: int
    players: list[PlayerScoreResponse]


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


def get_round_response(
    room: GameRoom,
    game_round: GameRound,
) -> RoundResponse:
    return RoundResponse(
        id=game_round.id,
        room_code=room.room_code,
        round_number=game_round.round_number,
        drawer_player_id=game_round.drawer_player_id,
        started_at=game_round.started_at,
        ended_at=game_round.ended_at,
    )


def build_scoreboard(db: Session, room_id: int) -> list[dict]:
    players = (
        db.query(Player)
        .filter(
            Player.room_id == room_id,
            Player.left_at.is_(None),
        )
        .order_by(Player.score.desc(), Player.joined_at.asc())
        .all()
    )

    return [
        {
            "player_id": player.id,
            "display_name": player.display_name,
            "score": player.score,
        }
        for player in players
    ]


def require_drawer(
    game_round: GameRound,
    current_player: Player,
) -> None:
    if game_round.drawer_player_id != current_player.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned drawer can perform this action.",
        )


@router.post(
    "/rooms/{room_code}/start",
    response_model=RoundResponse,
)
@limiter.limit("5/minute")
async def start_game(
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

    if room.status != "waiting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This room has already started or finished.",
        )

    players = get_active_players(db, room.id)

    if len(players) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least two players are required.",
        )

    if not all(player.is_ready for player in players):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All players must be ready before starting.",
        )

    room.status = "playing"
    room.current_round = 1
    room.started_at = datetime.utcnow()
    room.ended_at = None

    db.commit()
    db.refresh(room)

    game_round = start_round(db, room)
    start_round_timer(room.id, game_round.round_number)

    await manager.broadcast(
        room.room_code,
        {
            "type": "game_started",
            "room_code": room.room_code,
            "current_round": game_round.round_number,
            "total_rounds": room.total_rounds,
            "drawer_player_id": game_round.drawer_player_id,
            "started_at": game_round.started_at.isoformat(),
        },
    )

    return get_round_response(room, game_round)


@router.post(
    "/rooms/{room_code}/rounds/current",
    response_model=RoundResponse,
)
@limiter.limit("10/minute")
async def initialize_current_round(
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
        .first()
    )

    if game_round is None:
        game_round = start_round(db, room)

    elif game_round.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The current round has already ended.",
        )

    start_round_timer(room.id, game_round.round_number)

    return get_round_response(room, game_round)


@router.get(
    "/rooms/{room_code}/rounds/current",
    response_model=RoundResponse,
)
def get_current_round(
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

    game_round = (
        db.query(GameRound)
        .filter(
            GameRound.room_id == room.id,
            GameRound.round_number == room.current_round,
        )
        .first()
    )

    if game_round is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current round exists.",
        )

    return get_round_response(room, game_round)


@router.get(
    "/rooms/{room_code}/rounds/current/drawer/{player_id}",
    response_model=DrawerRoundResponse,
)
def get_round_for_player(
    room_code: str,
    player_id: int,
    current_player: Player = Depends(get_current_player_in_room),
    db: Session = Depends(get_db),
):
    room = get_room_or_404(db, room_code)

    if current_player.room_id != room.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this room.",
        )

    if current_player.id != player_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own drawer information.",
        )

    if current_player.left_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are no longer an active player.",
        )

    game_round = (
        db.query(GameRound)
        .filter(
            GameRound.room_id == room.id,
            GameRound.round_number == room.current_round,
        )
        .first()
    )

    if game_round is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current round exists.",
        )

    require_drawer(game_round, current_player)

    if game_round.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The round has already ended.",
        )

    return DrawerRoundResponse(
        id=game_round.id,
        room_code=room.room_code,
        round_number=game_round.round_number,
        drawer_player_id=game_round.drawer_player_id,
        started_at=game_round.started_at,
        ended_at=game_round.ended_at,
        word=game_round.word,
    )


@router.get(
    "/rooms/{room_code}/scores",
    response_model=ScoreboardResponse,
)
def get_scoreboard(
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

    players = (
        db.query(Player)
        .filter(
            Player.room_id == room.id,
            Player.left_at.is_(None),
        )
        .order_by(Player.score.desc(), Player.joined_at.asc())
        .all()
    )

    return ScoreboardResponse(
        room_code=room.room_code,
        status=room.status,
        current_round=room.current_round,
        total_rounds=room.total_rounds,
        players=[
            PlayerScoreResponse(
                player_id=player.id,
                display_name=player.display_name,
                score=player.score,
                is_ready=player.is_ready,
            )
            for player in players
        ],
    )


@router.post(
    "/rooms/{room_code}/rounds/advance",
    response_model=RoundAdvanceResponse,
)
@limiter.limit("5/minute")
async def advance_round(
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
        .first()
    )

    if game_round is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current round exists.",
        )

    # Only the assigned drawer can manually end the current round.
    require_drawer(game_round, current_player)

    if game_round.ended_at is None:
        # finish_round fetches the current round itself.
        game_round = finish_round(db, room)

    cancel_round_timer(room.id)
    db.refresh(room)
    db.refresh(game_round)

    scoreboard = build_scoreboard(db, room.id)

    await manager.broadcast(
        room.room_code,
        {
            "type": "round_ended",
            "round_number": game_round.round_number,
            "drawer_player_id": game_round.drawer_player_id,
            "word": game_round.word,
            "reason": "manual_advance",
            "scoreboard": scoreboard,
        },
    )

    if room.status == "completed":
        result = save_game_result(db, room)

        if result is not None:
            scoreboard = result.final_scores
            winner = next(
                (
                    item
                    for item in scoreboard
                    if item["player_id"] == result.winner_player_id
                ),
                None,
            )
        else:
            winner = scoreboard[0] if scoreboard else None

        await manager.broadcast(
            room.room_code,
            {
                "type": "game_completed",
                "room_code": room.room_code,
                "total_rounds": room.total_rounds,
                "scoreboard": scoreboard,
                "winner": winner,
            },
        )

        message = "Game completed and results saved."
    else:
        message = "Round finished. The next round will be initialized."

    return RoundAdvanceResponse(
        room_code=room.room_code,
        status=room.status,
        current_round=room.current_round,
        total_rounds=room.total_rounds,
        message=message,
    )