"""
工单05: 多轮对话上下文存储 — 轻量级内存实现

支持:
  - 按 conversation_id 存储/读取最近 N 轮对话
  - TTL 自动过期（默认30分钟）
  - 线程安全（Lock）
"""

import time
from collections import OrderedDict
from threading import Lock


class ConversationStore:
    """内存对话历史存储"""

    def __init__(self, max_history: int = 10, ttl_seconds: int = 1800) -> None:
        self._max_history = max_history
        self._ttl = ttl_seconds
        self._store: dict[str, OrderedDict] = {}
        self._lock = Lock()

    def add_turn(self, conversation_id: str, question: str, answer: str = "") -> None:
        """添加一轮对话"""
        with self._lock:
            if conversation_id not in self._store:
                self._store[conversation_id] = OrderedDict()
            history = self._store[conversation_id]
            key = f"turn_{int(time.time() * 1000)}"
            history[key] = {
                "question": question,
                "answer": answer,
                "timestamp": time.time(),
            }
            while len(history) > self._max_history:
                history.popitem(last=False)

    def update_last_answer(self, conversation_id: str, answer: str) -> None:
        """更新最后一轮的答案（生成答案后回填）"""
        with self._lock:
            history = self._store.get(conversation_id)
            if not history:
                return
            last_key = next(reversed(history))
            history[last_key]["answer"] = answer

    def get_history(self, conversation_id: str, max_turns: int = 5) -> list[dict]:
        """获取最近 N 轮对话历史（自动清理过期记录）"""
        with self._lock:
            history = self._store.get(conversation_id)
            if not history:
                return []

            now = time.time()
            expired = [k for k, v in history.items() if now - v["timestamp"] > self._ttl]
            for k in expired:
                del history[k]

            if not history:
                return []

            turns = list(history.values())
            return turns[-max_turns:]
