"""LLM API 封装，可 fallback。"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.agent.prompts import SYSTEM_PROMPT
from app.config import settings


class LLMClient:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    def is_enabled(self) -> bool:
        return bool(settings.use_llm and settings.llm_base_url and settings.llm_api_key)

    def extract_intent_and_slots(self, query: str) -> dict[str, Any] | None:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        if not self.is_enabled():
            return None
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {
                    "role": "user",
                    "content": (
                        "请输出 JSON，字段包含 intent、patient_name、department_name、doctor_name、"
                        "date_expr、time_expr、slot_type、history_condition。用户输入：" + query
                    ),
                },
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = httpx.post(
                settings.llm_base_url.rstrip("/") + "/chat/completions",
                headers=headers,
                json=payload,
                timeout=settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception:
            return None
