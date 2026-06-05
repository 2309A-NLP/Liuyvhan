import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.core.config import settings


class Base(DeclarativeBase):
    pass


class FeedbackRecord(Base):
    __tablename__ = "rag_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_mode: Mapped[str] = mapped_column(String(32))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeedbackService:
    def __init__(self) -> None:
        self.engine = None
        self.file_path = Path(settings.exports_dir / "feedback.jsonl")
        if settings.mysql_enabled:
            self.engine = create_engine(settings.mysql_dsn, pool_pre_ping=True)
            Base.metadata.create_all(self.engine)

    def save_feedback(self, payload: dict) -> str:
        if self.engine is not None:
            with Session(self.engine) as session:
                record = FeedbackRecord(**payload)
                session.add(record)
                session.commit()
            return "mysql"

        with self.file_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return "jsonl"
