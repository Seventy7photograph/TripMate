# 文件说明：LLM Provider：mock。
import json
import re
import time
from datetime import date
from decimal import Decimal, InvalidOperation

from app.providers.llm.base import LlmRequest, LlmResponse, LlmUsage

_CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


class MockLlmProvider:
    """Deterministic structured-output provider for local development and tests."""

    provider_name = "mock"
    model_name = "mock-tripbrief-v1"

    async def generate(self, request: LlmRequest) -> LlmResponse:
        started = time.perf_counter()
        content = self._extract(request.user_text)
        payload = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        latency_ms = max(1, int((time.perf_counter() - started) * 1_000))
        return LlmResponse(
            content=payload,
            usage=LlmUsage(
                input_tokens=max(1, len(request.user_prompt) // 3),
                output_tokens=max(1, len(payload) // 3),
                latency_ms=latency_ms,
                model_name=self.model_name,
            ),
        )

    def _extract(self, text: str) -> dict[str, object]:
        start_date, end_date = self._extract_dates(text)
        origin = self._extract_origin(text)
        destination = self._extract_destination(text)
        party_size = self._extract_party_size(text)
        budget_minor = self._extract_budget_minor(text)
        interests = [
            interest
            for interest in ("美食", "城市漫步", "历史", "博物馆", "摄影", "自然", "夜景")
            if interest in text
        ]

        return {
            "destination": destination,
            "origin": origin,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "party_size": party_size,
            "budget_minor": budget_minor,
            "currency": "CNY",
            "interests": interests,
            "pace": (
                "relaxed"
                if any(word in text for word in ("轻松", "悠闲", "慢节奏"))
                else "intensive"
                if any(word in text for word in ("紧凑", "特种兵", "赶"))
                else "balanced"
            ),
            "transport_preferences": [],
            "lodging_preferences": [],
            "must_visit": [],
            "avoid": [],
            "constraints": [],
        }

    @staticmethod
    def _extract_dates(text: str) -> tuple[date | None, date | None]:
        match = re.search(
            r"(?P<start_year>\d{4})年(?P<start_month>\d{1,2})月(?P<start_day>\d{1,2})日"
            r"(?:到|至|—|-|~)"
            r"(?:(?P<end_year>\d{4})年)?"
            r"(?P<end_month>\d{1,2})月(?P<end_day>\d{1,2})日",
            text,
        )
        if match is None:
            return None, None
        try:
            start = date(
                int(match.group("start_year")),
                int(match.group("start_month")),
                int(match.group("start_day")),
            )
            end = date(
                int(match.group("end_year") or match.group("start_year")),
                int(match.group("end_month")),
                int(match.group("end_day")),
            )
        except ValueError:
            return None, None
        return start, end

    @staticmethod
    def _extract_origin(text: str) -> str | None:
        match = re.search(
            r"从(?P<origin>[\u4e00-\u9fa5]{2,12}?)(?:出发)?(?:去|到|前往)",
            text,
        )
        return match.group("origin") if match else None

    @staticmethod
    def _extract_destination(text: str) -> str | None:
        match = re.search(
            r"(?:去|到|前往)(?P<destination>[\u4e00-\u9fa5]{2,12}?)"
            r"(?=，|,|。|；|;|\s|预算|\d|[一二两三四五六七八九十]个?人)",
            text,
        )
        return match.group("destination") if match else None

    @staticmethod
    def _extract_party_size(text: str) -> int | None:
        match = re.search(
            r"(?<![\d一二两三四五六七八九十])"
            r"(?P<count>\d{1,2}|[一二两三四五六七八九十])"
            r"(?:个)?人",
            text,
        )
        if match is None:
            return None
        raw = match.group("count")
        return int(raw) if raw.isdigit() else _CHINESE_NUMBERS[raw]

    @staticmethod
    def _extract_budget_minor(text: str) -> int | None:
        match = re.search(
            r"预算(?:大约|约|是)?\s*"
            r"(?P<amount>\d+(?:\.\d{1,2})?)\s*(?:元|块|人民币|CNY)",
            text,
            flags=re.IGNORECASE,
        )
        if match is None:
            return None
        try:
            return int(Decimal(match.group("amount")) * 100)
        except (InvalidOperation, ValueError):
            return None
