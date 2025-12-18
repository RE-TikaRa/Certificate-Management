from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import select

from ..data.database import Database
from ..data.models import AIProvider
from .settings_service import SettingsService


@dataclass(frozen=True)
class AIProviderInfo:
    id: int
    name: str
    api_base: str
    api_keys: str
    model: str
    pdf_pages: int
    last_key_index: int


def _split_api_keys(raw: str) -> list[str]:
    keys: list[str] = []
    for chunk in raw.replace("\n", ",").split(","):
        item = chunk.strip()
        if not item:
            continue
        if "|" in item:
            _name, value = item.split("|", 1)
            item = value.strip()
        if item:
            keys.append(item)
    return keys


def _clamp_int(value: str, *, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value.strip())
    except Exception:
        return default
    return max(min_value, min(max_value, parsed))


def _normalize_api_base(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("API 地址格式不正确，请填写 http(s) URL")
    return value.rstrip("/")


class AIProviderService:
    ACTIVE_KEY = "ai_active_provider_id"

    def __init__(self, db: Database, settings: SettingsService) -> None:
        self._db = db
        self._settings = settings

    def ensure_legacy_migration(self) -> None:
        """
        若旧版使用 settings 表保存单一 AI 配置且当前还没有 provider，则迁移为一个默认 provider。
        """
        with self._db.session_scope() as session:
            count = session.scalar(select(AIProvider).limit(1))
            if count is not None:
                return

            api_base = _normalize_api_base(self._settings.get("ai_api_base", ""))
            api_key = self._settings.get("ai_api_key", "").strip()
            model = self._settings.get("ai_model", "").strip()
            pdf_pages = _clamp_int(self._settings.get("ai_pdf_pages", "1"), default=1, min_value=1, max_value=10)

            if not any([api_base, api_key, model]):
                provider = AIProvider(name="默认", api_base="", api_keys="", model="", pdf_pages=1, last_key_index=-1)
            else:
                provider = AIProvider(
                    name="默认",
                    api_base=api_base.rstrip("/"),
                    api_keys=api_key,
                    model=model,
                    pdf_pages=pdf_pages,
                    last_key_index=-1,
                )
            session.add(provider)
            session.flush()
            self._settings.set_in_session(session, self.ACTIVE_KEY, str(provider.id))

    def list_providers(self) -> list[AIProviderInfo]:
        with self._db.session_scope() as session:
            rows = session.scalars(select(AIProvider).order_by(AIProvider.id.asc())).all()
            return [
                AIProviderInfo(
                    id=row.id,
                    name=row.name,
                    api_base=row.api_base,
                    api_keys=row.api_keys,
                    model=row.model,
                    pdf_pages=row.pdf_pages,
                    last_key_index=row.last_key_index,
                )
                for row in rows
            ]

    def get_active_provider_id(self) -> int | None:
        raw = self._settings.get(self.ACTIVE_KEY, "").strip()
        if not raw:
            return None
        try:
            return int(raw)
        except Exception:
            return None

    def set_active_provider_id(self, provider_id: int) -> None:
        self._settings.set(self.ACTIVE_KEY, str(provider_id))

    def get_active_provider(self) -> AIProviderInfo:
        providers = self.list_providers()
        if not providers:
            self.ensure_legacy_migration()
            providers = self.list_providers()
        active = self.get_active_provider_id()
        if active is None and providers:
            self.set_active_provider_id(providers[0].id)
            return providers[0]
        for p in providers:
            if p.id == active:
                if p.api_base and "://" not in p.api_base:
                    normalized = _normalize_api_base(p.api_base)
                    self.update_provider(p.id, api_base=normalized)
                    return AIProviderInfo(
                        id=p.id,
                        name=p.name,
                        api_base=normalized,
                        api_keys=p.api_keys,
                        model=p.model,
                        pdf_pages=p.pdf_pages,
                        last_key_index=p.last_key_index,
                    )
                return p
        if providers:
            self.set_active_provider_id(providers[0].id)
            return providers[0]
        raise ValueError("未配置 AI Provider")

    def create_provider(
        self,
        *,
        name: str,
        api_base: str,
        api_keys: str,
        model: str,
        pdf_pages: int,
    ) -> AIProviderInfo:
        with self._db.session_scope() as session:
            row = AIProvider(
                name=name.strip() or "未命名",
                api_base=_normalize_api_base(api_base),
                api_keys=api_keys.strip(),
                model=model.strip(),
                pdf_pages=max(1, min(10, int(pdf_pages))),
                last_key_index=-1,
            )
            session.add(row)
            session.flush()
            return AIProviderInfo(
                id=row.id,
                name=row.name,
                api_base=row.api_base,
                api_keys=row.api_keys,
                model=row.model,
                pdf_pages=row.pdf_pages,
                last_key_index=row.last_key_index,
            )

    def update_provider(
        self,
        provider_id: int,
        *,
        name: str | None = None,
        api_base: str | None = None,
        api_keys: str | None = None,
        model: str | None = None,
        pdf_pages: int | None = None,
        reset_rotation: bool = False,
    ) -> None:
        with self._db.session_scope() as session:
            row = session.get(AIProvider, provider_id)
            if row is None:
                raise ValueError("Provider 不存在")
            if name is not None:
                row.name = name.strip() or row.name
            if api_base is not None:
                row.api_base = _normalize_api_base(api_base)
            if api_keys is not None:
                row.api_keys = api_keys.strip()
            if model is not None:
                row.model = model.strip()
            if pdf_pages is not None:
                row.pdf_pages = max(1, min(10, int(pdf_pages)))
            if reset_rotation:
                row.last_key_index = -1

    def delete_provider(self, provider_id: int) -> None:
        with self._db.session_scope() as session:
            row = session.get(AIProvider, provider_id)
            if row is None:
                return
            session.delete(row)

        active = self.get_active_provider_id()
        if active == provider_id:
            providers = self.list_providers()
            self._settings.set(self.ACTIVE_KEY, str(providers[0].id) if providers else "")

    def get_rotated_api_key(self, provider_id: int) -> str:
        with self._db.session_scope() as session:
            row = session.get(AIProvider, provider_id)
            if row is None:
                raise ValueError("Provider 不存在")
            keys = _split_api_keys(row.api_keys)
            if not keys:
                raise ValueError("请先填写 API Key")
            if len(keys) == 1:
                return keys[0]

            last = row.last_key_index
            next_index = 0 if last < 0 or last >= len(keys) else (last + 1) % len(keys)
            row.last_key_index = next_index
            session.add(row)
            return keys[next_index]
