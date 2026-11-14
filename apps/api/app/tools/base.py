# 文件说明：Agent 受控工具：base。
import asyncio
import hashlib
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar

T = TypeVar("T")


class ToolLimitExceeded(Exception):
    pass


class ToolDeadlineExceeded(Exception):
    pass


class ToolTimeoutError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ToolCallAudit:
    tool_name: str
    provider: str
    input_hash: str
    status: str
    latency_ms: int
    estimated_cost_minor: int
    error_code: str | None = None


class ToolRunner:
    def __init__(
        self,
        *,
        max_calls: int,
        deadline: datetime,
        _parent: "ToolRunner | None" = None,
    ) -> None:
        self._parent: ToolRunner | None = _parent
        self._max_calls: int = max_calls
        self._deadline: datetime = (
            _parent._deadline if _parent is not None else deadline
        )
        self._call_count: int = 0
        self.audits: list[ToolCallAudit] = (
            _parent.audits if _parent is not None else []
        )

    @property
    def call_count(self) -> int:
        return self._call_count

    def scoped(self, *, max_calls: int) -> "ToolRunner":
        return ToolRunner(
            max_calls=max_calls,
            deadline=self._deadline,
            _parent=self,
        )

    async def call(
        self,
        *,
        tool_name: str,
        provider: str,
        input_payload: dict[str, object],
        operation: Callable[[], Awaitable[T]],
        estimated_cost_minor: int = 0,
        timeout_seconds: float | None = None,
        max_retries: int = 0,
    ) -> T:
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0 or max_retries > 3:
            raise ValueError("max_retries must be between 0 and 3")

        input_hash = _input_hash(input_payload)
        self._ensure_call_available(
            tool_name=tool_name,
            provider=provider,
            input_hash=input_hash,
        )
        self._commit_call()
        started = time.perf_counter()
        attempts = 0
        while True:
            remaining = (self._deadline - datetime.now(UTC)).total_seconds()
            if remaining <= 0:
                self.audits.append(
                    ToolCallAudit(
                        tool_name=tool_name,
                        provider=provider,
                        input_hash=input_hash,
                        status="error",
                        latency_ms=max(
                            1,
                            int((time.perf_counter() - started) * 1_000),
                        ),
                        estimated_cost_minor=estimated_cost_minor,
                        error_code="graph_timeout",
                    )
                )
                raise ToolDeadlineExceeded
            attempt_timeout = (
                remaining
                if timeout_seconds is None
                else min(remaining, timeout_seconds)
            )
            try:
                async with asyncio.timeout(attempt_timeout):
                    result = await operation()
                break
            except TimeoutError as exc:
                if attempts < max_retries:
                    attempts += 1
                    continue
                self.audits.append(
                    ToolCallAudit(
                        tool_name=tool_name,
                        provider=provider,
                        input_hash=input_hash,
                        status="error",
                        latency_ms=max(
                            1,
                            int((time.perf_counter() - started) * 1_000),
                        ),
                        estimated_cost_minor=estimated_cost_minor,
                        error_code=(
                            "graph_timeout"
                            if timeout_seconds is None
                            else "tool_timeout"
                        ),
                    )
                )
                raise ToolTimeoutError from exc
            except Exception as exc:
                if attempts < max_retries:
                    attempts += 1
                    continue
                self.audits.append(
                    ToolCallAudit(
                        tool_name=tool_name,
                        provider=provider,
                        input_hash=input_hash,
                        status="error",
                        latency_ms=max(
                            1,
                            int((time.perf_counter() - started) * 1_000),
                        ),
                        estimated_cost_minor=estimated_cost_minor,
                        error_code=getattr(exc, "code", "tool_error"),
                    )
                )
                raise

        self.audits.append(
            ToolCallAudit(
                tool_name=tool_name,
                provider=provider,
                input_hash=input_hash,
                status="success",
                latency_ms=max(1, int((time.perf_counter() - started) * 1_000)),
                estimated_cost_minor=estimated_cost_minor,
            )
        )
        return result

    def _ensure_call_available(
        self,
        *,
        tool_name: str,
        provider: str,
        input_hash: str,
    ) -> None:
        if self._call_count >= self._max_calls:
            self.audits.append(
                ToolCallAudit(
                    tool_name=tool_name,
                    provider=provider,
                    input_hash=input_hash,
                    status="error",
                    latency_ms=0,
                    estimated_cost_minor=0,
                    error_code="tool_limit_exceeded",
                )
            )
            raise ToolLimitExceeded
        if self._parent is not None:
            self._parent._ensure_call_available(
                tool_name=tool_name,
                provider=provider,
                input_hash=input_hash,
            )

    def _commit_call(self) -> None:
        self._call_count += 1
        if self._parent is not None:
            self._parent._commit_call()


def _input_hash(payload: dict[str, object]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(serialized.encode()).hexdigest()
