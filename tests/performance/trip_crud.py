# 文件说明：性能测试脚本：trip_crud。
import argparse
import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx


@dataclass(slots=True)
class Metrics:
    durations_ms: list[float] = field(default_factory=list)
    requests: int = 0
    failures: int = 0

    def record(self, duration_ms: float, *, ok: bool) -> None:
        self.requests += 1
        self.durations_ms.append(duration_ms)
        if not ok:
            self.failures += 1


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(len(ordered) * ratio) - 1)
    return ordered[index]


def trip_payload(index: int) -> dict[str, object]:
    return {
        "brief": {
            "destination": f"Perf City {index}",
            "origin": "Shanghai",
            "start_date": "2026-12-01",
            "end_date": "2026-12-03",
            "party_size": 2,
            "budget_minor": 500_000,
            "currency": "CNY",
            "interests": ["food"],
            "pace": "balanced",
            "transport_preferences": [],
            "lodging_preferences": [],
            "must_visit": [],
            "avoid": [],
            "constraints": [],
        }
    }


async def timed(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    metrics: Metrics,
    *,
    expected_status: int,
    headers: dict[str, str],
    json_body: dict[str, object] | None = None,
) -> httpx.Response | None:
    started = time.perf_counter()
    try:
        response = await client.request(
            method,
            path,
            headers=headers,
            json=json_body,
        )
        elapsed = (time.perf_counter() - started) * 1_000
        metrics.record(elapsed, ok=response.status_code == expected_status)
        return response if response.status_code == expected_status else None
    except httpx.HTTPError:
        metrics.record((time.perf_counter() - started) * 1_000, ok=False)
        return None


async def worker(
    *,
    client: httpx.AsyncClient,
    token: str,
    deadline: float,
    metrics: Metrics,
    worker_id: int,
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    iteration = 0
    while time.monotonic() < deadline:
        iteration += 1
        created = await timed(
            client,
            "POST",
            "/trips",
            metrics,
            expected_status=201,
            headers=headers,
            json_body=trip_payload(worker_id * 100_000 + iteration),
        )
        if created is None:
            continue
        trip_id = str(created.json()["id"])
        await timed(
            client,
            "GET",
            "/trips",
            metrics,
            expected_status=200,
            headers=headers,
        )
        await timed(
            client,
            "GET",
            f"/trips/{trip_id}",
            metrics,
            expected_status=200,
            headers=headers,
        )
        updated = await timed(
            client,
            "PATCH",
            f"/trips/{trip_id}",
            metrics,
            expected_status=200,
            headers=headers,
            json_body={"expected_version": 1, "status": "ready"},
        )
        if updated is not None:
            await timed(
                client,
                "DELETE",
                f"/trips/{trip_id}?expected_version=2",
                metrics,
                expected_status=204,
                headers=headers,
            )
        await asyncio.sleep(0.05)


async def run(args: argparse.Namespace) -> dict[str, object]:
    base_url = args.base_url.rstrip("/")
    email = f"perf-{uuid4().hex}@example.com"
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        registration = await client.post(
            "/auth/register",
            json={
                "email": email,
                "password": "correct-horse-battery-staple",
                "display_name": "Performance Runner",
            },
        )
        registration.raise_for_status()
        token = str(registration.json()["access_token"])

        metrics = Metrics()
        warmup_headers = {"Authorization": f"Bearer {token}"}
        for index in range(2):
            created = await client.post(
                "/trips",
                headers=warmup_headers,
                json=trip_payload(10_000 + index),
            )
            created.raise_for_status()
            trip_id = str(created.json()["id"])
            await client.delete(
                f"/trips/{trip_id}?expected_version=1",
                headers=warmup_headers,
            )

        deadline = time.monotonic() + args.duration
        await asyncio.gather(
            *[
                worker(
                    client=client,
                    token=token,
                    deadline=deadline,
                    metrics=metrics,
                    worker_id=index + 1,
                )
                for index in range(args.vus)
            ]
        )

    p95 = percentile(metrics.durations_ms, 0.95)
    failure_rate = (
        metrics.failures / metrics.requests if metrics.requests else 1.0
    )
    summary: dict[str, object] = {
        "created_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "vus": args.vus,
        "duration_seconds": args.duration,
        "requests": metrics.requests,
        "failures": metrics.failures,
        "failure_rate": round(failure_rate, 6),
        "p50_ms": round(percentile(metrics.durations_ms, 0.50), 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(percentile(metrics.durations_ms, 0.99), 2),
        "thresholds": {
            "p95_ms": args.threshold_p95_ms,
            "failure_rate": args.max_failure_rate,
        },
        "passed": (
            p95 < args.threshold_p95_ms
            and failure_rate < args.max_failure_rate
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="TripMate CRUD performance smoke")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010/api/v1")
    parser.add_argument("--vus", type=int, default=5)
    parser.add_argument("--duration", type=float, default=10)
    parser.add_argument("--threshold-p95-ms", type=float, default=500)
    parser.add_argument("--max-failure-rate", type=float, default=0.01)
    parser.add_argument(
        "--output",
        default=str(
            Path("output")
            / "performance"
            / f"trip-crud-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.json"
        ),
    )
    summary = asyncio.run(run(parser.parse_args()))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
