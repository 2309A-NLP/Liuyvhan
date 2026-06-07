import json

import redis

from app.core.config import settings


class CacheService:
    def __init__(self) -> None:
        self.client = None
        try:
            self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            self.client.ping()
        except Exception:
            self.client = None

    def get(self, key: str) -> dict | None:
        if not self.client:
            return None
        value = self.client.get(key)
        if not value:
            return None
        return json.loads(value)

    def set(self, key: str, payload: dict) -> None:
        if not self.client:
            return
        self.client.setex(key, settings.redis_cache_ttl, json.dumps(payload, ensure_ascii=False))
