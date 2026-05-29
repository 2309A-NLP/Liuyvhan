from types import SimpleNamespace

import pytest

from core.llm_client import LLMClient
from core.retriever import Retriever
from models.schemas import RetrievedChunk, RoleProfile
from modules.role_prompts import build_system_prompt


def test_system_prompt_prioritizes_current_question() -> None:
    role = RoleProfile(
        role_id="psychologist",
        name="Support Guide",
        domain="mental health",
        description="Provide grounded emotional support.",
        personality="Calm and structured.",
        tone="Warm but direct.",
        system_rules=["Stay grounded in the user's actual question."],
        prompt_template="unused",
        metadata={},
    )

    prompt = build_system_prompt(
        role=role,
        user_message="How can I sleep better when I am stressed?",
        short_memory=[{"role": "user", "content": "I have been tired lately."}],
        long_memory=[{"content": "The user often struggles with bedtime.", "source": "memory"}],
        references=[
            RetrievedChunk(
                doc_id="doc-1",
                title="Sleep routine",
                content="Reduce caffeine late in the day and keep a stable bedtime.",
                source="guide",
                score=0.88,
            )
        ],
    )

    assert "Current user question:" in prompt
    assert "How can I sleep better when I am stressed?" in prompt
    assert "Answer the current user question first." in prompt
    assert "If memory is not relevant, ignore it." in prompt


def test_system_prompt_clips_large_context_blocks() -> None:
    role = RoleProfile(
        role_id="psychologist",
        name="Support Guide",
        domain="mental health",
        description="Provide grounded emotional support.",
        personality="Calm and structured.",
        tone="Warm but direct.",
        system_rules=["Stay grounded in the user's actual question."],
        prompt_template="unused",
        metadata={},
    )

    prompt = build_system_prompt(
        role=role,
        user_message="What should I do next?",
        short_memory=[{"role": "assistant", "content": "A" * 800}],
        long_memory=[{"content": "B" * 800, "source": "memory"}],
        references=[
            RetrievedChunk(
                doc_id="doc-1",
                title="Long note",
                content="C" * 1200,
                source="guide",
                score=0.88,
            )
        ],
    )

    assert "A" * 400 not in prompt
    assert "B" * 400 not in prompt
    assert "C" * 400 not in prompt


def test_mock_generation_changes_with_question() -> None:
    settings = SimpleNamespace(
        llm_provider="mock",
        llm_model_name="mock-character",
        llm_api_base="",
        llm_api_key="",
        llm_timeout=30,
        llm_max_tokens=1024,
        llm_temperature=0.35,
        llm_top_p=0.9,
        llm_presence_penalty=0.2,
    )
    client = LLMClient(settings, logger=SimpleNamespace(info=lambda *args, **kwargs: None))
    role = SimpleNamespace(role_id="psychologist")
    references = [
        RetrievedChunk(
            doc_id="doc-1",
            title="Sleep routine",
            content="Keep a stable bedtime and reduce caffeine after lunch.",
            source="guide",
            score=0.91,
        ),
        RetrievedChunk(
            doc_id="doc-2",
            title="Stress journal",
            content="Write down triggers and notice what happens before anxiety rises.",
            source="guide",
            score=0.72,
        ),
    ]

    answer_sleep = client.generate(
        role=role,
        message="How can I sleep better?",
        short_memory=[],
        long_memory=[],
        references=references,
        system_prompt="unused",
    )
    answer_stress = client.generate(
        role=role,
        message="How can I reduce anxiety at work?",
        short_memory=[],
        long_memory=[],
        references=references,
        system_prompt="unused",
    )

    assert answer_sleep != answer_stress
    assert "How can I sleep better" in answer_sleep
    assert "How can I reduce anxiety at work" in answer_stress


def test_mock_generation_splits_multiple_questions() -> None:
    settings = SimpleNamespace(
        llm_provider="mock",
        llm_model_name="mock-character",
        llm_api_base="",
        llm_api_key="",
        llm_timeout=30,
        llm_max_tokens=1024,
        llm_temperature=0.35,
        llm_top_p=0.9,
        llm_presence_penalty=0.2,
    )
    client = LLMClient(settings, logger=SimpleNamespace(info=lambda *args, **kwargs: None))
    role = SimpleNamespace(role_id="wealth_advisor")

    answer = client.generate(
        role=role,
        message="How should I build an emergency fund? How much cash should I keep?",
        short_memory=[],
        long_memory=[],
        references=[
            RetrievedChunk(
                doc_id="doc-3",
                title="Emergency fund",
                content="Start by defining fixed monthly spending and target three to six months of coverage.",
                source="guide",
                score=0.86,
            )
        ],
        system_prompt="unused",
    )

    assert "1. " in answer
    assert "2. " in answer
    assert "多个子问题" in answer


class _FakeEmbeddingService:
    def embed_text(self, text: str) -> list[float]:
        return [float(len(text) or 1)]


class _FakeMilvusClient:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, collection_name, query_vector, query_text, top_k, filters):  # noqa: ANN001
        self.queries.append(query_text)
        return [
            {
                "doc_id": "doc-1",
                "title": "Prompt tuning",
                "content": "Answer the current question directly before expanding.",
                "source": "notes",
                "score": 0.72,
            },
            {
                "doc_id": "doc-1",
                "title": "Prompt tuning",
                "content": "Answer the current question directly before expanding.",
                "source": "notes",
                "score": 0.65,
            },
            {
                "doc_id": "doc-2",
                "title": "Unrelated",
                "content": "This is not about prompts.",
                "source": "notes",
                "score": 0.05,
            },
        ]


class _FakeRerankService:
    def rerank(self, query: str, candidates: list[dict], top_n: int) -> list[dict]:
        ranked = []
        for item in candidates:
            enriched = dict(item)
            enriched["rerank_score"] = enriched["score"]
            ranked.append(enriched)
        ranked.sort(key=lambda item: item["rerank_score"], reverse=True)
        return ranked[:top_n]


def test_retriever_expands_query_and_filters_noise() -> None:
    settings = SimpleNamespace(
        knowledge_collection="role_knowledge",
        retrieval_top_k=6,
        rerank_top_n=4,
        retrieval_query_variants=3,
        retrieval_min_score=0.18,
    )
    milvus = _FakeMilvusClient()
    retriever = Retriever(
        settings=settings,
        milvus_client=milvus,
        embedding_service=_FakeEmbeddingService(),
        rerank_service=_FakeRerankService(),
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
    )

    results = retriever.retrieve("请问 如何优化提示词？", role_id="psychologist")

    assert len(milvus.queries) >= 2
    assert len(results) == 1
    assert results[0].doc_id == "doc-1"


def test_openai_compatible_generation_uses_configured_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "live answer"}}]}

    def fake_post(url, json, headers, timeout):  # noqa: ANN001
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr("core.llm_client.requests.post", fake_post)
    settings = SimpleNamespace(
        llm_provider="siliconflow",
        llm_model_name="Qwen/Qwen2.5-7B-Instruct",
        llm_api_base="https://api.siliconflow.cn/v1",
        llm_api_key="secret",
        llm_timeout=30,
        llm_max_tokens=1024,
        llm_temperature=0.35,
        llm_top_p=0.9,
        llm_presence_penalty=0.2,
    )
    client = LLMClient(settings, logger=SimpleNamespace(info=lambda *args, **kwargs: None))

    answer = client.generate(
        role=SimpleNamespace(role_id="virtual_friend"),
        message="hello",
        short_memory=[],
        long_memory=[],
        references=[],
        system_prompt="system prompt",
    )

    assert answer == "live answer"
    assert captured["url"] == "https://api.siliconflow.cn/v1/chat/completions"
    assert captured["json"] == {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "messages": [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "hello"},
        ],
        "max_tokens": 1024,
        "temperature": 0.35,
        "top_p": 0.9,
        "presence_penalty": 0.2,
    }
    assert captured["headers"] == {
        "Authorization": "Bearer secret",
        "Content-Type": "application/json",
    }
    assert captured["timeout"] == 30


def test_openai_compatible_stream_generation_yields_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _Response:
        encoding = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def raise_for_status(self) -> None:
            return None

        def iter_lines(self, decode_unicode: bool = False):  # noqa: FBT001, FBT002
            assert decode_unicode is False
            return iter(
                [
                    b'data: {"choices":[{"delta":{"content":"live "}}]}',
                    b'data: {"choices":[{"delta":{"content":"answer"}}]}',
                    b"data: [DONE]",
                ]
            )

    def fake_post(url, json, headers, timeout, stream):  # noqa: ANN001
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        captured["stream"] = stream
        return _Response()

    monkeypatch.setattr("core.llm_client.requests.post", fake_post)
    settings = SimpleNamespace(
        llm_provider="siliconflow",
        llm_model_name="Qwen/Qwen2.5-7B-Instruct",
        llm_api_base="https://api.siliconflow.cn/v1",
        llm_api_key="secret",
        llm_timeout=30,
        llm_max_tokens=1024,
        llm_temperature=0.35,
        llm_top_p=0.9,
        llm_presence_penalty=0.2,
    )
    client = LLMClient(settings, logger=SimpleNamespace(info=lambda *args, **kwargs: None))

    chunks = list(
        client.generate_stream(
            role=SimpleNamespace(role_id="virtual_friend"),
            message="hello",
            short_memory=[],
            long_memory=[],
            references=[],
            system_prompt="system prompt",
        )
    )

    assert chunks == ["live ", "answer"]
    assert captured["url"] == "https://api.siliconflow.cn/v1/chat/completions"
    assert captured["json"]["stream"] is True
    assert captured["stream"] is True


def test_openai_compatible_stream_generation_decodes_utf8_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Response:
        encoding = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def raise_for_status(self) -> None:
            return None

        def iter_lines(self, decode_unicode: bool = False):  # noqa: FBT001, FBT002
            assert decode_unicode is False
            return iter(
                [
                    b'data: {"choices":[{"delta":{"content":"\xe4\xbd\xa0\xe5\xa5\xbd"}}]}',
                    b'data: {"choices":[{"delta":{"content":"\xef\xbc\x8c\xe4\xb8\x96\xe7\x95\x8c"}}]}',
                    b"data: [DONE]",
                ]
            )

    def fake_post(url, json, headers, timeout, stream):  # noqa: ANN001
        return _Response()

    monkeypatch.setattr("core.llm_client.requests.post", fake_post)
    settings = SimpleNamespace(
        llm_provider="siliconflow",
        llm_model_name="Qwen/Qwen2.5-7B-Instruct",
        llm_api_base="https://api.siliconflow.cn/v1",
        llm_api_key="secret",
        llm_timeout=30,
        llm_max_tokens=1024,
        llm_temperature=0.35,
        llm_top_p=0.9,
        llm_presence_penalty=0.2,
    )
    client = LLMClient(settings, logger=SimpleNamespace(info=lambda *args, **kwargs: None))

    chunks = list(
        client.generate_stream(
            role=SimpleNamespace(role_id="virtual_friend"),
            message="你好",
            short_memory=[],
            long_memory=[],
            references=[],
            system_prompt="system prompt",
        )
    )

    assert chunks == ["你好", "，世界"]
