
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Player(Base):
    __tablename__ = "players"

    __table_args__ = (
        UniqueConstraint(
            "room_id",
            "display_name",
            name="uq_player_room_display_name",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("game_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(
        String(40), nullable=False
    )
    score: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    is_ready: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    room: Mapped["GameRoom"] = relationship(
        back_populates="players"
    )
    guesses: Mapped[list["Guess"]] = relationship(
        back_populates="player"
    )
    drawn_rounds: Mapped[list["GameRound"]] = relationship(
        back_populates="drawer",
        foreign_keys="GameRound.drawer_player_id",
    )
