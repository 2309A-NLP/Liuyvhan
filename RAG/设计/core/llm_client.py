from __future__ import annotations
"""
LLMClient 负责与大语言模型（如 GPT-4、ChatGLM 等）通信，发送提示词并获取回答
"""
import json
import re
import textwrap
from collections.abc import Iterator
from typing import Any

import requests

from utils.text_sanitizer import (
    looks_corrupted_text,
    normalize_text,
    prefers_chinese_reply,
    strip_generation_artifacts,
)


class LLMClient:
    """大模型调用层。

    它只关心一件事：把已经准备好的 system prompt 和 user message
    发给上游模型，再把返回结果清洗成项目内部可用的答案。
    """

    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger

    def generate(
        self,
        role,
        message: str,
        short_memory: list[dict],
        long_memory: list[dict],
        references: list,
        system_prompt: str,
    ) -> str:
        # mock 模式用于本地断网、无 key 或调试链路时兜底。
        if self.settings.llm_provider == "mock":
            answer = self._generate_mock(role, message, short_memory, long_memory, references)
            return normalize_text(answer)

        # 真正接模型时，只把“系统提示词 + 当前用户问题”直接送到上游。
        # 短期记忆、长期记忆、检索知识已经提前被塞进 system_prompt 里了。
        answer = self._generate_openai_compatible(system_prompt, message)
        return self._finalize_answer(
            answer=answer,
            role=role,
            message=message,
            short_memory=short_memory,
            long_memory=long_memory,
            references=references,
        )

    def generate_stream(
        self,
        role,
        message: str,
        short_memory: list[dict],
        long_memory: list[dict],
        references: list,
        system_prompt: str,
    ) -> Iterator[str]:
        if self.settings.llm_provider == "mock":
            answer = self._generate_mock(role, message, short_memory, long_memory, references)
            yield from self._stream_mock_answer(normalize_text(answer))
            return

        # 当前流式实现是“上游流式收集 + 本地统一清洗 + 再切块输出”。
        # 好处是前端拿到的 chunk 更干净，代价是失去最原始的逐 token 直通。
        answer = self._collect_openai_compatible_stream(system_prompt, message)
        finalized = self._finalize_answer(
            answer=answer,
            role=role,
            message=message,
            short_memory=short_memory,
            long_memory=long_memory,
            references=references,
        )
        yield from self._stream_mock_answer(finalized, chunk_size=32)

    def _generate_mock(
        self,
        role,
        message: str,
        short_memory: list[dict],
        long_memory: list[dict],
        references: list,
    ) -> str:
        sub_questions = self._split_questions(message)
        opening = self._role_opening(role.role_id)
        evidence = self._build_evidence_pool(message, references, long_memory)
        sections = [opening]

        if len(sub_questions) > 1:
            sections.append("你这次输入里包含多个子问题，我按问题拆开回答。")
            for index, question in enumerate(sub_questions, start=1):
                sections.append(f"{index}. {self._answer_question(question, evidence)}")
        else:
            sections.append(self._answer_question(sub_questions[0], evidence))

        if evidence:
            sections.append("依据线索：")
            for item in evidence[:2]:
                sections.append(f"- {item}")
        else:
            sections.append("这次检索到的资料和历史信息都不够贴近当前问题，所以我先给你一个通用但可执行的判断框架。")

        recent_context = self._recent_user_context(short_memory)
        if recent_context:
            sections.append(f"和你最近提到的内容相比，这次更聚焦在：{recent_context}")

        sections.append(self._follow_up(message, evidence))
        return "\n".join(sections).strip()

    def _generate_openai_compatible(self, system_prompt: str, message: str) -> str:
        if not self.settings.llm_api_base:
            raise RuntimeError("LLM_API_BASE is empty. Configure the upstream chat API endpoint first.")
        if not self.settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is empty. Configure a valid API key first.")

        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_openai_payload(system_prompt, message)
        endpoint = f"{self.settings.llm_api_base.rstrip('/')}/chat/completions"
        self.logger.info(
            "Calling LLM provider=%s model=%s endpoint=%s",
            self.settings.llm_provider,
            self.settings.llm_model_name,
            endpoint,
        )

        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.settings.llm_timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", "n/a")
            response_text = self._truncate_response_text(getattr(response, "text", ""))
            raise RuntimeError(
                f"Upstream LLM request failed: provider={self.settings.llm_provider}, "
                f"model={self.settings.llm_model_name}, status={status_code}, body={response_text}"
            ) from exc

        data = response.json()
        # 这里按 OpenAI-compatible 返回格式取 choices[0].message.content。
        content = self._extract_message_content(data)
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(
                f"Upstream LLM response is empty: {self._truncate_response_text(str(data))}"
            )
        return content.strip()

    def _collect_openai_compatible_stream(self, system_prompt: str, message: str) -> str:
        if not self.settings.llm_api_base:
            raise RuntimeError("LLM_API_BASE is empty. Configure the upstream chat API endpoint first.")
        if not self.settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is empty. Configure a valid API key first.")

        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_openai_payload(system_prompt, message, stream=True)
        endpoint = f"{self.settings.llm_api_base.rstrip('/')}/chat/completions"
        self.logger.info(
            "Streaming LLM provider=%s model=%s endpoint=%s",
            self.settings.llm_provider,
            self.settings.llm_model_name,
            endpoint,
        )

        parts: list[str] = []

        try:
            with requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.settings.llm_timeout,
                stream=True,
            ) as response:
                response.raise_for_status()
                response.encoding = getattr(response, "encoding", None) or "utf-8"
                for raw_line in response.iter_lines(decode_unicode=False):
                    if not raw_line:
                        continue
                    if isinstance(raw_line, bytes):
                        line = raw_line.decode("utf-8", errors="replace").strip()
                    else:
                        line = str(raw_line).strip()
                    if not line or not line.startswith("data:"):
                        continue

                    data_line = line[5:].strip()
                    if data_line == "[DONE]":
                        break

                    try:
                        data = json.loads(data_line)
                    except json.JSONDecodeError:
                        continue

                    content = self._extract_stream_content(data)
                    if content:
                        parts.append(content)
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", "n/a")
            response_text = self._truncate_response_text(getattr(response, "text", ""))
            raise RuntimeError(
                f"Upstream LLM stream failed: provider={self.settings.llm_provider}, "
                f"model={self.settings.llm_model_name}, status={status_code}, body={response_text}"
            ) from exc

        return "".join(parts).strip()

    def _build_openai_payload(self, system_prompt: str, message: str, *, stream: bool = False) -> dict[str, Any]:
        # 这个 payload 就是项目发给上游大模型的核心请求体。
        payload: dict[str, Any] = {
            "model": self.settings.llm_model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            "max_tokens": self.settings.llm_max_tokens,
            "temperature": self.settings.llm_temperature,
            "top_p": self.settings.llm_top_p,
            "presence_penalty": self.settings.llm_presence_penalty,
        }
        if stream:
            payload["stream"] = True
        return payload

    @staticmethod
    def _extract_message_content(data: dict[str, Any]) -> str:
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Upstream LLM response has unexpected shape: {LLMClient._truncate_response_text(str(data))}"
            ) from exc

    @staticmethod
    def _extract_stream_content(data: dict[str, Any]) -> str:
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError, TypeError):
            return ""

        delta = choice.get("delta") or {}
        content = delta.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ]
            return "".join(text_parts)

        message = choice.get("message") or {}
        fallback = message.get("content")
        if isinstance(fallback, str):
            return fallback
        return ""

    @staticmethod
    def _stream_mock_answer(answer: str, chunk_size: int = 24) -> Iterator[str]:
        text = answer.strip()
        if not text:
            return
        for index in range(0, len(text), chunk_size):
            yield text[index : index + chunk_size]

    def _finalize_answer(
        self,
        answer: str,
        role,
        message: str,
        short_memory: list[dict],
        long_memory: list[dict],
        references: list,
    ) -> str:
        expect_chinese = prefers_chinese_reply(message)
        # 先做一次统一清洗，去掉 <br>、response、assistant 等脏片段。
        cleaned = strip_generation_artifacts(answer, expect_chinese=expect_chinese)

        if looks_corrupted_text(cleaned, expect_chinese=expect_chinese):
            self.logger.warning(
                "Detected corrupted or low-quality LLM output for role=%s; falling back to local mock answer.",
                getattr(role, "role_id", "unknown"),
            )
            # 如果上游回答明显乱码或质量过差，就降级回本地 mock，
            # 保证前端至少拿到一个结构正常、可读的中文答案。
            cleaned = normalize_text(
                self._generate_mock(role, message, short_memory, long_memory, references)
            )

        if not cleaned:
            cleaned = normalize_text(
                self._generate_mock(role, message, short_memory, long_memory, references)
            )

        return cleaned

    @staticmethod
    def _truncate_response_text(text: Any, limit: int = 400) -> str:
        normalized = str(text).strip()
        if len(normalized) <= limit:
            return normalized
        return normalized[:limit] + "..."

    def _answer_question(self, question: str, evidence: list[str]) -> str:
        summary = self._summarize_message(question)
        if evidence:
            return (
                f"先直接回答：你这个问题的核心是“{summary}”。"
                f" 结合当前最相关的资料，我建议你优先围绕“{self._focus_from_evidence(evidence[0])}”处理，"
                "先确认现象、再判断原因、最后决定行动。"
            )
        return (
            f"先直接回答：你这个问题的核心是“{summary}”。"
            " 目前缺少足够贴合的资料支撑，所以更稳妥的做法是先界定目标、约束条件和你最在意的结果，"
            "再据此细化方案。"
        )

    def _build_evidence_pool(self, message: str, references: list, long_memory: list[dict]) -> list[str]:
        ranked: list[tuple[float, str]] = []
        for item in references[:4]:
            snippet = self._best_snippet(message, item.content)
            score = float(getattr(item, "score", 0.0))
            ranked.append((score + self._overlap_ratio(message, f"{item.title} {item.content}"), f"{item.title}: {snippet}"))

        for item in long_memory[:2]:
            content = item.get("content", "")
            snippet = self._best_snippet(message, content)
            ranked.append((self._overlap_ratio(message, content), f"历史偏好: {snippet}"))

        ranked.sort(key=lambda row: row[0], reverse=True)
        return [text for _, text in ranked if text]

    def _recent_user_context(self, short_memory: list[dict]) -> str:
        user_messages = [item.get("content", "").strip() for item in short_memory if item.get("role") == "user"]
        if len(user_messages) <= 1:
            return ""
        recent = [self._summarize_message(item) for item in user_messages[-2:]]
        if recent[-1] == recent[-2]:
            return recent[-1]
        return f"{recent[-2]}，以及这次的 {recent[-1]}"

    def _follow_up(self, message: str, evidence: list[str]) -> str:
        if evidence:
            return f"如果你愿意，我可以继续把“{self._summarize_message(message)}”拆成更细的步骤或清单。"
        return f"如果你补充一下场景、目标和限制条件，我可以把“{self._summarize_message(message)}”继续收敛成更具体的建议。"

    @staticmethod
    def _role_opening(role_id: str) -> str:
        openings = {
            "virtual_friend": "我先按朋友式的方式，直接回应你当前这个问题。",
            "psychologist": "我先按支持性分析的方式，围绕你当前这个问题来回答。",
            "legal_consultant": "我先按法律信息梳理的方式，针对你当前这个问题说明重点。",
            "wealth_advisor": "我先按风险和决策框架的方式，直接回答你当前这个问题。",
        }
        return openings.get(role_id, "我先围绕你当前这个问题，给出直接回答。")

    @staticmethod
    def _split_questions(message: str) -> list[str]:
        parts = [part.strip() for part in re.split(r"[?？!！;；\n]+", message) if part.strip()]
        return parts or [message.strip()]

    @staticmethod
    def _summarize_message(message: str) -> str:
        normalized = re.sub(r"\s+", " ", message).strip()
        if not normalized:
            return "当前问题"
        clipped = textwrap.shorten(normalized, width=32, placeholder="...")
        return clipped

    @staticmethod
    def _best_snippet(message: str, content: str) -> str:
        lines = [line.strip() for line in re.split(r"[。！？!?]\s*", content) if line.strip()]
        if not lines:
            return textwrap.shorten(content.strip(), width=72, placeholder="...")
        scored = sorted(
            lines,
            key=lambda line: LLMClient._overlap_ratio(message, line),
            reverse=True,
        )
        return textwrap.shorten(scored[0], width=72, placeholder="...")

    @staticmethod
    def _focus_from_evidence(evidence_line: str) -> str:
        if ":" in evidence_line:
            return evidence_line.split(":", 1)[0].strip()
        return textwrap.shorten(evidence_line, width=24, placeholder="...")

    @staticmethod
    def _overlap_ratio(left: str, right: str) -> float:
        left_terms = set(LLMClient._tokenize(left))
        right_terms = set(LLMClient._tokenize(right))
        if not left_terms or not right_terms:
            return 0.0
        return len(left_terms & right_terms) / max(len(left_terms), 1)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        cleaned = "".join(ch if ch.isalnum() else " " for ch in text.lower())
        words = [word for word in cleaned.split() if word]
        dense = "".join(words)
        ngrams = [dense[i : i + 2] for i in range(max(1, len(dense) - 1))] if dense else []
        return words + ngrams
