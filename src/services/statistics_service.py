from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..data.database import Database
from ..data.models import Award, AwardMember


class StatisticsService:
    def __init__(self, db: Database):
        self.db = db

    def get_overview(self) -> dict[str, Any]:
        """
        Get comprehensive statistics in a single query for performance.
        Previously executed 9 separate queries, now optimized to 1 main query + 1 for latest awards.
        """
        with self.db.session_scope() as session:
            from sqlalchemy import case

            # Single query for all statistics
            result = session.query(
                func.count(Award.id).label("total"),
                func.sum(case((Award.level == "国家级", 1), else_=0)).label("national"),
                func.sum(case((Award.level == "省级", 1), else_=0)).label("provincial"),
                func.sum(case((Award.level == "校级", 1), else_=0)).label("school"),
                func.sum(case((Award.rank == "一等奖", 1), else_=0)).label("first_prize"),
                func.sum(case((Award.rank == "二等奖", 1), else_=0)).label("second_prize"),
                func.sum(case((Award.rank == "三等奖", 1), else_=0)).label("third_prize"),
                func.sum(case((Award.rank == "优秀奖", 1), else_=0)).label("excellent_prize"),
            ).first()

            latest_awards = session.scalars(
                select(Award)
                .options(selectinload(Award.award_members).selectinload(AwardMember.member))
                .order_by(Award.award_date.desc())
                .limit(10)
            ).all()

        totals = {
            "total": int(result.total or 0) if result else 0,
            "national": int(result.national or 0) if result else 0,
            "provincial": int(result.provincial or 0) if result else 0,
            "school": int(result.school or 0) if result else 0,
            "first_prize": int(result.first_prize or 0) if result else 0,
            "second_prize": int(result.second_prize or 0) if result else 0,
            "third_prize": int(result.third_prize or 0) if result else 0,
            "excellent_prize": int(result.excellent_prize or 0) if result else 0,
        }

        return {**totals, "latest_awards": latest_awards}

    def get_group_by_level(self) -> dict[str, int]:
        with self.db.session_scope() as session:
            rows = session.execute(select(Award.level, func.count(Award.id)).group_by(Award.level)).all()
        pairs = [(level, count) for level, count in rows]
        return dict(pairs)

    def get_group_by_rank(self) -> dict[str, int]:
        with self.db.session_scope() as session:
            rows = session.execute(select(Award.rank, func.count(Award.id)).group_by(Award.rank)).all()
        pairs = [(rank, count) for rank, count in rows]
        return dict(pairs)

    def get_recent_by_month(self, months: int = 6) -> dict[str, int]:
        threshold = date.today().replace(day=1)
        with self.db.session_scope() as session:
            rows = session.execute(
                select(func.strftime("%Y-%m", Award.award_date), func.count(Award.id))
                .where(Award.award_date >= threshold)
                .group_by(func.strftime("%Y-%m", Award.award_date))
                .order_by(func.strftime("%Y-%m", Award.award_date))
            ).all()
        pairs = [(month, count) for month, count in rows]
        return dict(pairs)

    def get_award_level_statistics(self) -> dict[str, int]:
        """按等级详细分类统计荣誉"""
        with self.db.session_scope() as session:
            # 定义所有可能的等级及其查询条件
            level_categories = {
                "国奖": "国家级",
                "省奖": "省级",
                "校奖": "校级",
                "一等奖": "一等奖",
                "二等奖": "二等奖",
                "三等奖": "三等奖",
                "优秀奖": "优秀奖",
            }
            stats = {}
            for display_name, level_value in level_categories.items():
                count = session.scalar(select(func.count(Award.id)).where(Award.level == level_value)) or 0
                if count > 0:  # 仅添加有数据的等级
                    stats[display_name] = count

            # 也统计按rank分类的等级奖
            rank_categories = {
                "一等优秀奖": "一等优秀奖",
                "二等优秀奖": "二等优秀奖",
                "三等优秀奖": "三等优秀奖",
            }
            for display_name, rank_value in rank_categories.items():
                count = session.scalar(select(func.count(Award.id)).where(Award.rank == rank_value)) or 0
                if count > 0:
                    stats[display_name] = count

        return stats
