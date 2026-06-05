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

    def append_message(self, session_id: str, message: dict) -> None:
        if not self.client or not session_id:
            return

        key = self._build_memory_key(session_id)
        self.client.rpush(key, json.dumps(message, ensure_ascii=False))

        history_limit = max(settings.conversation_history_limit * 2, 2)
        current_length = self.client.llen(key)
        if current_length > history_limit:
            self.client.ltrim(key, current_length - history_limit, -1)

        self.client.expire(key, settings.redis_memory_ttl)

    def get_history(self, session_id: str, limit: int | None = None) -> list[dict]:
        if not self.client or not session_id:
            return []

        key = self._build_memory_key(session_id)
        raw_messages = self.client.lrange(key, 0, -1)
        if not raw_messages:
            return []

        messages = [json.loads(item) for item in raw_messages]
        turn_limit = limit or settings.conversation_history_limit
        message_limit = max(turn_limit * 2, 2)
        return messages[-message_limit:]

    def clear_history(self, session_id: str) -> None:
        if not self.client or not session_id:
            return
        self.client.delete(self._build_memory_key(session_id))

    def _build_memory_key(self, session_id: str) -> str:
        return f"rag-ticket01:memory:{session_id}"
