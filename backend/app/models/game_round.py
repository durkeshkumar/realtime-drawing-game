
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class GameRound(Base):
    __tablename__ = "game_rounds"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("game_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round_number: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    drawer_player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT"),
        nullable=False,
    )
    word: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    room: Mapped["GameRoom"] = relationship(back_populates="rounds")
    drawer: Mapped["Player"] = relationship(
        back_populates="drawn_rounds",
        foreign_keys=[drawer_player_id],
    )
    guesses: Mapped[list["Guess"]] = relationship(
        back_populates="round",
        cascade="all, delete-orphan",
    )
