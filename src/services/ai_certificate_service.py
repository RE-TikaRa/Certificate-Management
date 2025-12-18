import base64
import contextlib
import json
import logging
import re
from ast import literal_eval
from contextlib import suppress
from datetime import date
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, ValidationError, field_validator

from ..data.database import Database
from .ai_provider_service import AIProviderService
from .settings_service import SettingsService

logger = logging.getLogger(__name__)


class CertificateExtractedInfo(BaseModel):
    competition_name: str | None = None
    award_date: date | None = None
    level: str | None = None
    rank: str | None = None
    certificate_code: str | None = None
    member_names: list[str] = Field(default_factory=list)

    @field_validator("award_date", mode="before")
    @classmethod
    def _parse_award_date(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if not isinstance(value, str):
            return None
        s = value.strip()
        if not s:
            return None

        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return None
        with suppress(Exception):
            return date.fromisoformat(s)

        return None


def _detect_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def _clamp_int(value: str, *, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value.strip())
    except Exception:
        return default
    return max(min_value, min(max_value, parsed))


def _render_pdf_pages_to_pngs(pdf_path: Path, *, page_count: int) -> list[bytes]:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:
        raise ValueError("缺少 PDF 解析依赖：PyMuPDF（请先执行 uv sync 安装依赖）") from exc

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise ValueError("PDF 打开失败，文件可能损坏或被加密") from exc

    try:
        if doc.page_count <= 0:
            raise ValueError("PDF 没有可渲染的页面")
        count = max(1, min(int(doc.page_count), page_count))
        images: list[bytes] = []
        for index in range(count):
            page = doc.load_page(index)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            images.append(pix.tobytes("png"))
        return images
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF 渲染失败") from exc
    finally:
        with suppress(Exception):
            doc.close()


def _read_image_payloads(path: Path, *, pdf_pages: int) -> list[tuple[bytes, str]]:
    if not path.exists():
        raise ValueError("证书文件不存在")
    if path.suffix.lower() == ".pdf":
        return [(b, "image/png") for b in _render_pdf_pages_to_pngs(path, page_count=pdf_pages)]
    return [(path.read_bytes(), _detect_mime(path))]


def _extract_json_object(text: str) -> str:
    obj = _extract_json_object_like(text)
    return json.dumps(obj, ensure_ascii=False)


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip().lstrip("\ufeff")
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^\s*```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    return cleaned.strip()


def _remove_trailing_commas(text: str) -> str:
    # Remove trailing commas before } or ], repeatedly until stable.
    previous = None
    current = text
    while previous != current:
        previous = current
        current = re.sub(r",\s*([}\]])", r"\1", current)
    return current


def _escape_control_chars_in_strings(text: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
                out.append(ch)
                continue
            if ch == "\\":
                escaped = True
                out.append(ch)
                continue
            if ch == '"':
                in_string = False
                out.append(ch)
                continue
            if ch in {"\n", "\r", "\u2028", "\u2029"}:
                out.append("\\n")
                continue
            if ch == "\t":
                out.append("\\t")
                continue
            if ord(ch) < 0x20:
                out.append(f"\\u{ord(ch):04x}")
                continue
            out.append(ch)
            continue

        if ch == '"':
            in_string = True
        out.append(ch)
    return "".join(out)


def _scan_json_object_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    s = text
    start_indices = [i for i, ch in enumerate(s) if ch == "{"]
    for start in start_indices:
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(s)):
            ch = s[idx]
            if in_string:
                if escaped:
                    escaped = False
                    continue
                if ch == "\\":
                    escaped = True
                    continue
                if ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                depth += 1
                continue
            if ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(s[start : idx + 1])
                    break
                continue
    return candidates


def _extract_json_object_like(text: str) -> dict[str, Any]:
    cleaned = _strip_code_fences(text)
    candidates = _scan_json_object_candidates(cleaned)
    if not candidates:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end == -1:
            raise ValueError("模型输出疑似被截断（缺少 }）")
        if start != -1 and end > start:
            candidates = [cleaned[start : end + 1]]
        else:
            raise ValueError("模型输出不是有效的 JSON 对象")

    errors: list[str] = []
    for candidate in candidates:
        raw = _remove_trailing_commas(candidate.strip())
        raw = _escape_control_chars_in_strings(raw)
        with contextlib.suppress(Exception):
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        # Fallback: try Python literal dict (LLM often outputs single quotes/None/True/False)
        py_raw = raw
        py_raw = re.sub(r"\bnull\b", "None", py_raw, flags=re.IGNORECASE)
        py_raw = re.sub(r"\btrue\b", "True", py_raw, flags=re.IGNORECASE)
        py_raw = re.sub(r"\bfalse\b", "False", py_raw, flags=re.IGNORECASE)
        try:
            parsed2 = literal_eval(py_raw)
        except Exception as exc:
            errors.append(str(exc))
            continue
        if isinstance(parsed2, dict):
            return cast(dict[str, Any], parsed2)

    detail = "; ".join(errors[:3])
    raise ValueError(f"模型输出不是有效的 JSON 对象{f'（{detail}）' if detail else ''}")


def _normalize_level(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip()
    mapping = {
        "国家": "国家级",
        "国家级": "国家级",
        "省": "省级",
        "省级": "省级",
        "校": "校级",
        "校级": "校级",
    }
    return mapping.get(v, v if v in {"国家级", "省级", "校级"} else None)


def _normalize_rank(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip()
    mapping = {
        "一等": "一等奖",
        "一等奖": "一等奖",
        "二等": "二等奖",
        "二等奖": "二等奖",
        "三等": "三等奖",
        "三等奖": "三等奖",
        "优秀": "优秀奖",
        "优秀奖": "优秀奖",
    }
    return mapping.get(v, v if v in {"一等奖", "二等奖", "三等奖", "优秀奖"} else None)


def _dedupe_names(names: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        raw = str(name).strip()
        if not raw:
            continue
        parts = [p.strip() for p in re.split(r"[、,，;；/|\n\r\t]+", raw) if p.strip()]
        for cleaned in parts if parts else [raw]:
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(cleaned)
    return out


class AICertificateService:
    """
    OpenAI 兼容 Chat Completions（/v1/chat/completions）方式识别证书图片信息。
    """

    def __init__(self, db: Database, settings: SettingsService, providers: AIProviderService) -> None:
        self._db = db
        self._settings = settings
        self._providers = providers

    def _get_active(self) -> tuple[str, str, str, int, int]:
        provider = self._providers.get_active_provider()
        base = provider.api_base.strip()
        model = provider.model.strip()
        if not base or not model:
            raise ValueError("请先在“系统设置 → AI 证书识别”中填写 API 地址 / API Key / 模型")
        api_key = self._providers.get_rotated_api_key(provider.id)
        pdf_pages = max(1, min(10, int(provider.pdf_pages)))
        return base, api_key, model, pdf_pages, provider.id

    def extract_from_image(self, image_path: Path) -> CertificateExtractedInfo:
        base, api_key, model, _pdf_pages, _provider_id = self._get_active()

        if self._should_use_responses(base):
            url = self._build_responses_url(base)
            payload = self._build_responses_payload(model=model, file_path=image_path)
            data = self._post_json(url, api_key=api_key, payload=payload)
            content = self._extract_output_text(data)
        else:
            url = self._build_chat_completions_url(base)
            payload = self._build_payload(model=model, image_path=image_path)
            data = self._post_json(url, api_key=api_key, payload=payload)
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("模型返回为空（未获取到可解析内容）")

        try:
            payload_obj = _extract_json_object_like(content)
        except Exception as exc:
            preview = content.strip().replace("\r", "")
            preview = preview[:800]
            logger.warning("AI JSON parse failed (model=%s): %s", model, exc)
            logger.warning("AI raw output preview: %s", preview)
            if "模型输出不是有效的 JSON 对象" in str(exc):
                raise ValueError(
                    "模型输出不是有效的 JSON 对象。"
                    "这通常意味着：当前模型不支持图片/PDF输入，或被服务端降级为纯文本拒绝，或模型未按要求输出 JSON。\n"
                    f"模型原文预览（前 800 字符）：{preview}"
                ) from exc
            raise ValueError(f"模型输出无法解析为 JSON：{exc}\n模型原文预览（前 800 字符）：{preview}") from exc

        try:
            parsed = CertificateExtractedInfo.model_validate(payload_obj)
        except ValidationError as exc:
            raise ValueError(f"模型返回 JSON 结构不符合预期：{exc}") from exc

        parsed.level = _normalize_level(parsed.level)
        parsed.rank = _normalize_rank(parsed.rank)
        parsed.member_names = _dedupe_names(parsed.member_names)

        if parsed.competition_name is not None:
            parsed.competition_name = parsed.competition_name.strip() or None
        if parsed.certificate_code is not None:
            parsed.certificate_code = parsed.certificate_code.strip() or None

        return parsed

    def list_models(self) -> list[str]:
        provider = self._providers.get_active_provider()
        base = provider.api_base.strip()
        if not base:
            raise ValueError("请先填写 API 地址 / API Key")
        api_key = self._providers.get_rotated_api_key(provider.id)

        url = self._build_models_url(base)
        data = self._request_json(url, api_key=api_key, method="GET")
        items = data.get("data", [])
        if not isinstance(items, list):
            raise ValueError("模型列表返回格式异常（data 不是数组）")

        models: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id", None)
            if isinstance(model_id, str) and model_id.strip():
                models.append(model_id.strip())

        uniq = sorted(set(models))
        if not uniq:
            raise ValueError("未获取到模型列表（你的 API 可能不支持 /v1/models）")
        return uniq

    def check_latency(self) -> int:
        """
        进行一次极小请求以测试联通，并返回延迟（毫秒）。

        说明：
        - 若 /v1/models 不支持，可由调用方先尝试 list_models 再 fallback 到该方法。
        """
        base, api_key, model, _pdf_pages, _provider_id = self._get_active()
        start = perf_counter()

        if self._should_use_responses(base):
            url = self._build_responses_url(base)
            payload = {"model": model, "input": [{"role": "user", "content": [{"type": "input_text", "text": "ping"}]}]}
            data = self._post_json(url, api_key=api_key, payload=payload)
            _ = self._extract_output_text(data)
        else:
            url = self._build_chat_completions_url(base)
            payload = {
                "model": model,
                "temperature": 0,
                "max_tokens": 8,
                "messages": [{"role": "user", "content": "ping"}],
            }
            data = self._post_json(url, api_key=api_key, payload=payload)
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not isinstance(content, str):
                raise ValueError("AI 返回格式异常（未获取到 message.content）")

        return int((perf_counter() - start) * 1000)

    def ping(self) -> None:
        base, api_key, model, _pdf_pages, _provider_id = self._get_active()

        if self._should_use_responses(base):
            url = self._build_responses_url(base)
            payload = {"model": model, "input": [{"role": "user", "content": [{"type": "input_text", "text": "ping"}]}]}
            data = self._post_json(url, api_key=api_key, payload=payload)
            content = self._extract_output_text(data)
        else:
            url = self._build_chat_completions_url(base)
            payload = {
                "model": model,
                "temperature": 0,
                "max_tokens": 8,
                "messages": [{"role": "user", "content": "ping"}],
            }
            data = self._post_json(url, api_key=api_key, payload=payload)
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise ValueError("AI 返回格式异常（未获取到 message.content）")

    def _build_chat_completions_url(self, base: str) -> str:
        b = base.strip().rstrip("/")
        if "/chat/completions" in b:
            return b
        if b.endswith("/models") or "/v1/models" in b:
            b = b.split("/v1")[0]
        if not b.endswith("/v1"):
            b = f"{b}/v1"
        return f"{b}/chat/completions"

    def _build_responses_url(self, base: str) -> str:
        b = base.strip().rstrip("/")
        if b.endswith("/responses") or "/v1/responses" in b:
            return b
        if "/chat/completions" in b:
            b = b.split("/chat/completions")[0].rstrip("/")
        if b.endswith("/models") or "/v1/models" in b:
            b = b.split("/v1")[0].rstrip("/")
        if not b.endswith("/v1"):
            b = f"{b}/v1"
        return f"{b}/responses"

    def _build_models_url(self, base: str) -> str:
        b = base.strip().rstrip("/")
        if "/chat/completions" in b:
            b = b.split("/chat/completions")[0].rstrip("/")
        if b.endswith("/models"):
            return b
        if b.endswith("/v1"):
            return f"{b}/models"
        if "/v1/" in b:
            prefix = b.split("/v1/")[0].rstrip("/")
            return f"{prefix}/v1/models"
        return f"{b}/v1/models"

    def _should_use_responses(self, base: str) -> bool:
        try:
            parsed = urlparse(base)
        except Exception:
            return False
        host = (parsed.netloc or "").lower()
        return host == "api.openai.com"

    def _build_payload(self, *, model: str, image_path: Path) -> dict[str, Any]:
        provider = self._providers.get_active_provider()
        pdf_pages = max(1, min(10, int(provider.pdf_pages)))
        payloads = _read_image_payloads(image_path, pdf_pages=pdf_pages)

        system = (
            "你是一个证书信息抽取助手。只根据图片内容抽取信息，不要编造。"
            "输出必须是严格的 JSON 对象，不要使用 Markdown 代码块。"
            "日期请输出 ISO 格式 YYYY-MM-DD；不确定就用 null，如果日期只是到某年某月，那就将日期定在那个月一号。"
            "level 仅允许：国家级/省级/校级；不确定用 null。"
            "rank 仅允许：一等奖/二等奖/三等奖/优秀奖；不确定用 null。"
            "member_names 仅输出姓名数组（字符串），不确定就输出空数组。"
            "尽量从证书中识别：比赛/竞赛名称、获奖日期、证书编号、获奖等级、成员姓名。"
            "不要把学校/单位/主办方当成比赛名称；成员姓名只输出中文姓名或证书上出现的姓名。"
            "如出现区域赛/分赛区/赛区/选拔赛等类似表述，通常按省赛（省级）处理。"
            "如出现全国赛/全国总决赛/总决赛等类似表述，通常按国赛（国家级）处理。"
        )
        schema_hint = (
            "{"
            '"competition_name": string|null,'
            '"award_date": "YYYY-MM-DD"|null,'
            '"level": string|null,'
            '"rank": string|null,'
            '"certificate_code": string|null,'
            '"member_names": string[]'
            "}"
        )
        user_text = f"请从这张证书图片中抽取以下字段并按 JSON 输出：{schema_hint}"

        content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        for image_bytes, mime in payloads:
            b64 = base64.b64encode(image_bytes).decode("ascii")
            data_url = f"data:{mime};base64,{b64}"
            content.append({"type": "image_url", "image_url": {"url": data_url}})

        return {
            "model": model,
            "temperature": 0,
            "max_tokens": 800,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": content,
                },
            ],
        }

    def _build_responses_payload(self, *, model: str, file_path: Path) -> dict[str, Any]:
        system = (
            "你是一个证书信息抽取助手。只根据证书内容抽取信息，不要编造。"
            "输出必须是严格的 JSON 对象，不要使用 Markdown 代码块。"
            "日期请输出 ISO 格式 YYYY-MM-DD；不确定就用 null，如果日期只是到某年某月，那就将日期定在那个月一号。"
            "level 仅允许：国家级/省级/校级；不确定用 null。"
            "rank 仅允许：一等奖/二等奖/三等奖/优秀奖；不确定用 null。"
            "member_names 仅输出姓名数组（字符串），不确定就输出空数组。"
            "尽量从证书中识别：比赛/竞赛名称、获奖日期、证书编号、获奖等级、成员姓名。"
            "不要把学校/单位/主办方当成比赛名称；成员姓名只输出中文姓名或证书上出现的姓名。"
            "如出现区域赛/分赛区/赛区/选拔赛等类似表述，通常按省赛（省级）处理。"
            "如出现全国赛/全国总决赛/总决赛等类似表述，通常按国赛（国家级）处理。"
        )
        schema_hint = (
            "{"
            '"competition_name": string|null,'
            '"award_date": "YYYY-MM-DD"|null,'
            '"level": string|null,'
            '"rank": string|null,'
            '"certificate_code": string|null,'
            '"member_names": string[]'
            "}"
        )
        user_text = f"请从该证书中抽取以下字段并按 JSON 输出：{schema_hint}"

        content: list[dict[str, Any]] = [{"type": "input_text", "text": user_text}]
        if file_path.suffix.lower() == ".pdf":
            b64 = base64.b64encode(file_path.read_bytes()).decode("ascii")
            content.append({"type": "input_file", "filename": file_path.name, "file_data": b64})
        else:
            payloads = _read_image_payloads(file_path, pdf_pages=1)
            image_bytes, mime = payloads[0]
            b64 = base64.b64encode(image_bytes).decode("ascii")
            data_url = f"data:{mime};base64,{b64}"
            content.append({"type": "input_image", "image_url": data_url})

        return {
            "model": model,
            "temperature": 0,
            "max_output_tokens": 800,
            "instructions": system,
            "input": [{"role": "user", "content": content}],
        }

    def _post_json(self, url: str, *, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(url, api_key=api_key, method="POST", payload=payload)

    def _extract_output_text(self, data: dict[str, Any]) -> str:
        text = data.get("output_text")
        if isinstance(text, str) and text.strip():
            return text

        output = data.get("output")
        if isinstance(output, list):
            parts: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content", None)
                if not isinstance(content, list):
                    continue
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") != "output_text":
                        continue
                    part_text = part.get("text", None)
                    if isinstance(part_text, str) and part_text:
                        parts.append(part_text)
            combined = "".join(parts).strip()
            if combined:
                return combined

        raise ValueError("模型返回为空（未获取到可解析内容）")

    def _request_json(
        self,
        url: str,
        *,
        api_key: str,
        method: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = b""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
        }
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = Request(url, data=body if payload is not None else None, headers=headers, method=method)
        try:
            with urlopen(req, timeout=60) as resp:
                raw = resp.read()
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            lower = detail.lower()
            if "error code: 1010" in lower or ("cloudflare" in lower and "1010" in lower):
                raise ValueError(
                    f"AI 请求失败：HTTP {exc.code} {exc.reason}（Cloudflare 1010 拒绝访问，通常是网络/代理/风控拦截）"
                ) from exc
            raise ValueError(f"AI 请求失败：HTTP {exc.code} {exc.reason} {detail}".strip()) from exc
        except URLError as exc:
            raise ValueError(f"AI 请求失败：{exc.reason}") from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            preview = raw.decode("utf-8", errors="replace").strip().replace("\r", "")
            preview = preview[:500]
            logger.warning("AI response is not JSON (url=%s): %s", url, preview)
            raise ValueError(f"AI 返回不是有效 JSON：{preview}") from exc
        if not isinstance(data, dict):
            raise ValueError("AI 返回格式异常（非对象）")
        if "error" in data:
            raise ValueError(f"AI 返回错误：{data['error']}")
        return data
