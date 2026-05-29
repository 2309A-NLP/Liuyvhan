from __future__ import annotations
"""
存短期记忆
"""
import json
from pathlib import Path
from typing import Any


class RedisClient:
    """短期记忆网关。

    上层只调用统一接口，不需要关心底层现在连的是真 Redis，
    还是本地 JSON 降级存储。
    """

    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self._backend = self._build_backend()
        self.storage_mode = self._backend.storage_mode

    def push_message(self, session_id: str, message: dict, max_items: int) -> None:
        self._backend.push_message(session_id, message, max_items)

    def get_messages(self, session_id: str) -> list[dict]:
        return self._backend.get_messages(session_id)

    def set_messages(self, session_id: str, messages: list[dict]) -> None:
        self._backend.set_messages(session_id, messages)

    def clear(self, session_id: str) -> None:
        self._backend.clear(session_id)

    def _build_backend(self):
        # 先尝试真 Redis，失败后自动降级到本地文件。
        if self.settings.redis_enabled:
            try:
                backend = _RemoteRedisBackend(self.settings, self.logger)
                self.logger.info(
                    "Redis backend=remote host=%s port=%s db=%s",
                    self.settings.redis_host,
                    self.settings.redis_port,
                    self.settings.redis_db,
                )
                return backend
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "Failed to initialize remote Redis at %s:%s/%s, falling back to local file store. reason=%s",
                    self.settings.redis_host,
                    self.settings.redis_port,
                    self.settings.redis_db,
                    exc,
                )

        self.logger.info("Redis backend=local-file path=%s", self.settings.local_redis_path)
        return _LocalRedisBackend(self.settings, self.logger)


class _LocalRedisBackend:
    storage_mode = "local-file"

    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.storage_path: Path = settings.local_redis_path
        self._cache: dict[str, list[dict]] = self._load_from_disk()

    def _load_from_disk(self) -> dict[str, list[dict]]:
        if not self.storage_path.exists():
            return {}
        return json.loads(self.storage_path.read_text(encoding="utf-8"))

    def _flush(self) -> None:
        self.storage_path.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def push_message(self, session_id: str, message: dict, max_items: int) -> None:
        history = self._cache.setdefault(session_id, [])
        history.append(message)
        if len(history) > max_items:
            del history[:-max_items]
        self._flush()
        self.logger.info(
            "Redis(local-file) message_saved session_id=%s total=%s path=%s",
            session_id,
            len(history),
            self.storage_path,
        )

    def get_messages(self, session_id: str) -> list[dict]:
        messages = list(self._cache.get(session_id, []))
        self.logger.info(
            "Redis(local-file) history_loaded session_id=%s total=%s",
            session_id,
            len(messages),
        )
        return messages

    def set_messages(self, session_id: str, messages: list[dict]) -> None:
        self._cache[session_id] = messages
        self._flush()
        self.logger.info(
            "Redis(local-file) history_rewritten session_id=%s total=%s",
            session_id,
            len(messages),
        )

    def clear(self, session_id: str) -> None:
        self._cache.pop(session_id, None)
        self._flush()
        self.logger.info("Redis(local-file) history_cleared session_id=%s", session_id)


class _RemoteRedisBackend:
    storage_mode = "redis"

    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        try:
            import redis
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError("redis package is not installed.") from exc

        self.redis = redis.Redis(
            host=self.settings.redis_host,
            port=self.settings.redis_port,
            db=self.settings.redis_db,
            decode_responses=True,
        )
        self.redis.ping()
        self.logger.info(
            "Redis(remote) connection_ready host=%s port=%s db=%s",
            self.settings.redis_host,
            self.settings.redis_port,
            self.settings.redis_db,
        )

    def push_message(self, session_id: str, message: dict, max_items: int) -> None:
        key = self._session_key(session_id)
        payload = json.dumps(message, ensure_ascii=False)
        # 使用 pipeline 把“追加 + 截断 + 计数”合并，减少往返。
        pipe = self.redis.pipeline()
        pipe.rpush(key, payload)
        pipe.ltrim(key, -max_items, -1)
        pipe.llen(key)
        _, _, total = pipe.execute()
        self.logger.info(
            "Redis(remote) message_saved session_id=%s total=%s",
            session_id,
            int(total),
        )

    def get_messages(self, session_id: str) -> list[dict]:
        key = self._session_key(session_id)
        raw_messages = self.redis.lrange(key, 0, -1)
        messages = [json.loads(item) for item in raw_messages]
        self.logger.info(
            "Redis(remote) history_loaded session_id=%s total=%s",
            session_id,
            len(messages),
        )
        return messages

    def set_messages(self, session_id: str, messages: list[dict]) -> None:
        key = self._session_key(session_id)
        pipe = self.redis.pipeline()
        pipe.delete(key)
        if messages:
            pipe.rpush(key, *[json.dumps(item, ensure_ascii=False) for item in messages])
        pipe.execute()
        self.logger.info(
            "Redis(remote) history_rewritten session_id=%s total=%s",
            session_id,
            len(messages),
        )

    def clear(self, session_id: str) -> None:
        self.redis.delete(self._session_key(session_id))
        self.logger.info("Redis(remote) history_cleared session_id=%s", session_id)

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"rag:session:{session_id}:messages"
