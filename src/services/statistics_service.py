from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy import func, select

from ..data.database import Database
from ..data.models import Award


class StatisticsService:
    def __init__(self, db: Database):
        self.db = db

    def get_overview(self) -> dict[str, Any]:
        with self.db.session_scope() as session:
            total = session.scalar(select(func.count(Award.id))) or 0
            national = session.scalar(select(func.count(Award.id)).where(Award.level == "国家级")) or 0
            provincial = session.scalar(select(func.count(Award.id)).where(Award.level == "省级")) or 0
            first_prize = session.scalar(select(func.count(Award.id)).where(Award.rank == "一等奖")) or 0
            latest_awards = (
                session.execute(select(Award).order_by(Award.award_date.desc()).limit(10)).scalars().all()
            )
        return {
            "total": total,
            "national": national,
            "provincial": provincial,
            "first_prize": first_prize,
            "latest_awards": latest_awards,
        }

    def get_group_by_level(self) -> dict[str, int]:
        with self.db.session_scope() as session:
            rows = session.execute(select(Award.level, func.count(Award.id)).group_by(Award.level)).all()
        return {level: count for level, count in rows}

    def get_group_by_rank(self) -> dict[str, int]:
        with self.db.session_scope() as session:
            rows = session.execute(select(Award.rank, func.count(Award.id)).group_by(Award.rank)).all()
        return {rank: count for rank, count in rows}

    def get_recent_by_month(self, months: int = 6) -> dict[str, int]:
        threshold = date.today().replace(day=1)
        with self.db.session_scope() as session:
            rows = session.execute(
                select(func.strftime("%Y-%m", Award.award_date), func.count(Award.id))
                .where(Award.award_date >= threshold)
                .group_by(func.strftime("%Y-%m", Award.award_date))
                .order_by(func.strftime("%Y-%m", Award.award_date))
            ).all()
        return {month: count for month, count in rows}
