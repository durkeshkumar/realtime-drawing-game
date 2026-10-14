
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class GameResult(Base):
    __tablename__ = "game_results"

    __table_args__ = (
        UniqueConstraint(
            "room_id",
            name="uq_game_results_room_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    room_id: Mapped[int] = mapped_column(
        ForeignKey("game_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    winner_player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    final_scores: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    completed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    room: Mapped["GameRoom"] = relationship()

    winner: Mapped["Player | None"] = relationship(
        foreign_keys=[winner_player_id],
    )
