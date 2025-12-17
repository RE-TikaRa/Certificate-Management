from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..data.database import Database
from ..data.models import AwardFlagValue, CustomFlag


class FlagService:
    """管理自定义布尔开关及其荣誉值。"""

    KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")

    def __init__(self, db: Database):
        self.db = db

    # ---- Flag definitions ----
    def list_flags(self, *, enabled_only: bool = False) -> list[CustomFlag]:
        with self.db.session_scope() as session:
            stmt = select(CustomFlag).order_by(CustomFlag.sort_order, CustomFlag.id)
            if enabled_only:
                stmt = stmt.where(CustomFlag.enabled.is_(True))
            return list(session.scalars(stmt).all())

    def get_defaults(self, *, enabled_only: bool = False) -> dict[str, bool]:
        return {flag.key: bool(flag.default_value) for flag in self.list_flags(enabled_only=enabled_only)}

    def create_flag(self, *, key: str, label: str, default_value: bool = False, enabled: bool = True) -> CustomFlag:
        self._validate_key(key)
        with self.db.session_scope() as session:
            # 自动排序到末尾
            max_order = (
                session.scalar(select(CustomFlag.sort_order).order_by(CustomFlag.sort_order.desc()).limit(1)) or 0
            )
            flag = CustomFlag(
                key=key,
                label=label,
                default_value=default_value,
                enabled=enabled,
                sort_order=int(max_order) + 1,
            )
            session.add(flag)
            session.flush()
            return flag

    def update_flag(
        self,
        flag_id: int,
        *,
        label: str | None = None,
        enabled: bool | None = None,
        default_value: bool | None = None,
        sort_order: int | None = None,
    ) -> CustomFlag:
        with self.db.session_scope() as session:
            flag = session.get(CustomFlag, flag_id)
            if not flag:
                raise ValueError(f"Flag {flag_id} not found")
            if label is not None:
                flag.label = label
            if enabled is not None:
                flag.enabled = enabled
            if default_value is not None:
                flag.default_value = default_value
            if sort_order is not None:
                flag.sort_order = sort_order
            session.flush()
            return flag

    def delete_flag(self, flag_id: int) -> None:
        with self.db.session_scope() as session:
            flag = session.get(CustomFlag, flag_id)
            if not flag:
                return
            session.execute(delete(AwardFlagValue).where(AwardFlagValue.flag_key == flag.key))
            session.delete(flag)

    # ---- Award flag values ----
    def set_award_flags(self, award_id: int, values: dict[str, bool], *, session: Session | None = None) -> None:
        if session is None:
            with self.db.session_scope() as s:
                self.set_award_flags(award_id, values, session=s)
                return

        session.execute(delete(AwardFlagValue).where(AwardFlagValue.award_id == award_id))
        rows = [AwardFlagValue(award_id=award_id, flag_key=key, value=bool(val)) for key, val in values.items()]
        if rows:
            session.add_all(rows)

    def get_award_flags(self, award_id: int, *, include_disabled: bool = False) -> dict[str, bool]:
        definitions = self.list_flags(enabled_only=not include_disabled)
        defaults = {flag.key: bool(flag.default_value) for flag in definitions}
        with self.db.session_scope() as session:
            rows = session.scalars(
                select(AwardFlagValue).where(AwardFlagValue.award_id == award_id, AwardFlagValue.flag_key.in_(defaults))
            ).all()
        for row in rows:
            defaults[row.flag_key] = bool(row.value)
        return defaults

    def get_flags_for_awards(
        self, award_ids: Iterable[int], *, include_disabled: bool = False
    ) -> dict[int, dict[str, bool]]:
        award_ids = list(award_ids)
        if not award_ids:
            return {}
        definitions = self.list_flags(enabled_only=not include_disabled)
        keys = [flag.key for flag in definitions]
        defaults = {flag.key: bool(flag.default_value) for flag in definitions}
        result: dict[int, dict[str, bool]] = {aid: dict(defaults) for aid in award_ids}
        with self.db.session_scope() as session:
            rows = session.execute(
                select(AwardFlagValue.award_id, AwardFlagValue.flag_key, AwardFlagValue.value)
                .where(AwardFlagValue.award_id.in_(award_ids))
                .where(AwardFlagValue.flag_key.in_(keys))
            ).all()
        for award_id, key, value in rows:
            result.setdefault(award_id, dict(defaults))[key] = bool(value)
        return result

    # ---- Helpers ----
    def _validate_key(self, key: str) -> None:
        if not self.KEY_PATTERN.match(key):
            raise ValueError("key 需为小写字母开头的 a-z0-9_，长度 2-64")
