
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Guess(Base):
    __tablename__ = "guesses"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    round_id: Mapped[int] = mapped_column(
        ForeignKey("game_rounds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    guess_text: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    round: Mapped["GameRound"] = relationship(back_populates="guesses")
    player: Mapped["Player"] = relationship(back_populates="guesses")
