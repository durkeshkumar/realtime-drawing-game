
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class GameRoom(Base):
    __tablename__ = "game_rooms"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )
    room_code: Mapped[str] = mapped_column(
        String(8),
        unique=True,
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="waiting",
        nullable=False,
    )
    current_round: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_rounds: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    players: Mapped[list["Player"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
    )
    rounds: Mapped[list["GameRound"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
    )
