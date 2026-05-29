from __future__ import annotations

import asyncio
import os
import time

import httpx


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
TOTAL_REQUESTS = 20
CONCURRENCY = 5


async def send_one(client: httpx.AsyncClient, index: int) -> float:
    started = time.perf_counter()
    response = await client.post(
        "/chat",
        json={
            "session_id": f"stress-session-{index}",
            "user_id": f"stress-user-{index}",
            "role_id": "virtual_friend",
            "message": "今天有点累，陪我聊聊。",
        },
    )
    response.raise_for_status()
    return time.perf_counter() - started


async def main() -> None:
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        async def runner(idx: int) -> float:
            async with semaphore:
                return await send_one(client, idx)

        durations = await asyncio.gather(*(runner(i) for i in range(TOTAL_REQUESTS)))

    total = sum(durations)
    qps = round(TOTAL_REQUESTS / total, 4) if total else 0.0
    print(
        {
            "total_requests": TOTAL_REQUESTS,
            "concurrency": CONCURRENCY,
            "avg_latency_seconds": round(total / TOTAL_REQUESTS, 4),
            "qps": qps,
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
