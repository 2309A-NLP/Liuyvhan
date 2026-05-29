from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import SETTINGS


@dataclass(slots=True)
class RetrievalMetrics:
    returned_doc_ids: list[str]
    hit_count: int
    precision: float | None
    recall: float | None
    mrr: float | None


@dataclass(slots=True)
class AnswerMetrics:
    keyword_hit_rate: float | None
    reference_doc_ids: list[str]
    reference_hit_count: int
    reference_precision: float | None
    reference_recall: float | None
    answer_length: int
    memory_size: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the RAG pipeline with separate retrieval, reference, and answer metrics."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("all", "retrieval", "chat"),
        default="all",
        help="Choose whether to run retrieval-only, chat-only, or both layers.",
    )
    parser.add_argument(
        "--dataset",
        default=str(SETTINGS.eval_seed_path),
        help="Path to the evaluation dataset JSON file.",
    )
    parser.add_argument(
        "--reload-knowledge",
        action="store_true",
        help="Reload demo knowledge before evaluation so the corpus matches the seed files.",
    )
    parser.add_argument(
        "--user-id",
        default="eval-user",
        help="User id used for chat evaluation requests.",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="HTTP base URL for a running service, for example http://127.0.0.1:8001.",
    )
    return parser.parse_args()


def keyword_hit_rate(answer: str, expected_keywords: list[str]) -> float | None:
    normalized_keywords = [keyword for keyword in expected_keywords if keyword]
    if not normalized_keywords:
        return None
    hits = sum(1 for keyword in normalized_keywords if keyword in answer)
    return round(hits / len(normalized_keywords), 4)


def safe_round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def average(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 4)


def normalize_expected_doc_ids(raw_ids: list[Any] | None) -> list[str]:
    return [str(item).strip() for item in (raw_ids or []) if str(item).strip()]


def normalize_doc_id(doc_id: str) -> str:
    value = str(doc_id).strip()
    if "-chunk-" in value:
        return value.split("-chunk-", 1)[0]
    return value


def infer_expected_doc_ids(
    knowledge_docs: list[dict[str, Any]],
    *,
    role_id: str,
    expected_keywords: list[str],
) -> list[str]:
    normalized_keywords = [keyword for keyword in expected_keywords if keyword]
    if not normalized_keywords:
        return []

    matched_docs: list[tuple[int, str]] = []
    for doc in knowledge_docs:
        if doc.get("role_id") != role_id:
            continue
        haystack = f"{doc.get('title', '')}\n{doc.get('content', '')}"
        hit_count = sum(1 for keyword in normalized_keywords if keyword in haystack)
        if hit_count > 0:
            matched_docs.append((hit_count, str(doc.get("doc_id", "")).strip()))

    matched_docs.sort(key=lambda item: (-item[0], item[1]))
    return [doc_id for _, doc_id in matched_docs if doc_id]


def choose_ground_truth_doc_ids(
    item: dict[str, Any],
    knowledge_docs: list[dict[str, Any]],
) -> tuple[list[str], str]:
    explicit = normalize_expected_doc_ids(item.get("expected_doc_ids"))
    if explicit:
        return explicit, "explicit"

    inferred = infer_expected_doc_ids(
        knowledge_docs,
        role_id=str(item["role_id"]),
        expected_keywords=[str(keyword) for keyword in item.get("expected_keywords", [])],
    )
    if inferred:
        return inferred, "inferred_from_keywords"

    return [], "missing"


def evaluate_retrieval(
    returned_doc_ids: list[str],
    *,
    ground_truth_doc_ids: list[str],
) -> RetrievalMetrics:
    normalized_returned = [normalize_doc_id(doc_id) for doc_id in returned_doc_ids]
    normalized_ground_truth = {normalize_doc_id(doc_id) for doc_id in ground_truth_doc_ids}
    hits = [doc_id for doc_id in normalized_returned if doc_id in normalized_ground_truth]
    hit_count = len(hits)

    precision = None
    recall = None
    mrr = None
    if ground_truth_doc_ids:
        precision = hit_count / max(len(returned_doc_ids), 1)
        recall = hit_count / len(ground_truth_doc_ids)
        for index, doc_id in enumerate(returned_doc_ids, start=1):
            if doc_id in ground_truth_doc_ids:
                mrr = 1 / index
                break

    return RetrievalMetrics(
        returned_doc_ids=returned_doc_ids,
        hit_count=hit_count,
        precision=safe_round(precision),
        recall=safe_round(recall),
        mrr=safe_round(mrr),
    )


def evaluate_chat_case(
    client: TestClient,
    *,
    user_id: str,
    case_index: int,
    question: str,
    role_id: str,
    expected_keywords: list[str],
    expected_reference_doc_ids: list[str],
) -> AnswerMetrics:
    payload = client.chat(
        session_id=f"eval-session-{case_index}",
        user_id=user_id,
        role_id=role_id,
        message=question,
    )

    reference_doc_ids = [
        normalize_doc_id(str(reference.get("doc_id", "")).strip())
        for reference in payload.get("references", [])
        if str(reference.get("doc_id", "")).strip()
    ]
    normalized_expected_reference_doc_ids = {
        normalize_doc_id(doc_id) for doc_id in expected_reference_doc_ids
    }
    reference_hit_count = sum(
        1 for doc_id in reference_doc_ids if doc_id in normalized_expected_reference_doc_ids
    )

    reference_precision = None
    reference_recall = None
    if expected_reference_doc_ids:
        reference_precision = reference_hit_count / max(len(reference_doc_ids), 1)
        reference_recall = reference_hit_count / len(normalized_expected_reference_doc_ids)

    return AnswerMetrics(
        keyword_hit_rate=keyword_hit_rate(
            str(payload.get("answer", "")),
            [str(keyword) for keyword in expected_keywords],
        ),
        reference_doc_ids=reference_doc_ids,
        reference_hit_count=reference_hit_count,
        reference_precision=safe_round(reference_precision),
        reference_recall=safe_round(reference_recall),
        answer_length=len(str(payload.get("answer", ""))),
        memory_size=int(payload.get("memory_size", 0)),
    )


def summarize_report(details: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    retrieval_rows = [row["retrieval"] for row in details if row.get("retrieval")]
    answer_rows = [row["answer"] for row in details if row.get("answer")]

    summary: dict[str, Any] = {
        "mode": mode,
        "cases": len(details),
        "retrieval": {
            "evaluable_cases": len(retrieval_rows),
            "average_precision": average([row["precision"] for row in retrieval_rows]),
            "average_recall": average([row["recall"] for row in retrieval_rows]),
            "average_mrr": average([row["mrr"] for row in retrieval_rows]),
        },
        "answer": {
            "evaluable_cases": len(answer_rows),
            "average_keyword_hit_rate": average(
                [row["keyword_hit_rate"] for row in answer_rows]
            ),
            "average_reference_precision": average(
                [row["reference_precision"] for row in answer_rows]
            ),
            "average_reference_recall": average(
                [row["reference_recall"] for row in answer_rows]
            ),
            "average_answer_length": average(
                [float(row["answer_length"]) for row in answer_rows]
            ),
        },
    }
    return summary


def main() -> None:
    args = parse_args()
    dataset_path = Path(args.dataset)
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    knowledge_docs = json.loads(Path(SETTINGS.knowledge_seed_path).read_text(encoding="utf-8"))

    details: list[dict[str, Any]] = []
    if args.base_url:
        client = HttpClient(args.base_url.rstrip("/"))
        client.reload_knowledge() if args.reload_knowledge else None
        client.create_user(args.user_id, "RAG Evaluation User")
        runner = client
    else:
        from fastapi.testclient import TestClient
        from main import app

        runner = LocalClient(TestClient(app))

    with runner:
        for index, item in enumerate(dataset, start=1):
            question = str(item["question"])
            role_id = str(item["role_id"])
            expected_keywords = [str(keyword) for keyword in item.get("expected_keywords", [])]
            ground_truth_doc_ids, ground_truth_source = choose_ground_truth_doc_ids(
                item,
                knowledge_docs,
            )
            expected_reference_doc_ids = normalize_expected_doc_ids(
                item.get("expected_reference_doc_ids")
            ) or ground_truth_doc_ids

            case_result: dict[str, Any] = {
                "case": index,
                "role_id": role_id,
                "question": question,
                "ground_truth_doc_ids": ground_truth_doc_ids,
                "ground_truth_source": ground_truth_source,
            }

            if args.mode in {"all", "retrieval"}:
                retrieval_source = runner.chat(
                    session_id=f"eval-session-{index}",
                    user_id=args.user_id,
                    role_id=role_id,
                    message=question,
                )
                retrieval_metrics = evaluate_retrieval(
                    [str(item.get("doc_id", "")).strip() for item in retrieval_source.get("references", []) if str(item.get("doc_id", "")).strip()],
                    ground_truth_doc_ids=ground_truth_doc_ids,
                )
                case_result["retrieval"] = asdict(retrieval_metrics)
                case_result["retrieval_source"] = "chat_references"

            if args.mode in {"all", "chat"}:
                answer_metrics = evaluate_chat_case(
                    runner,
                    user_id=args.user_id,
                    case_index=index,
                    question=question,
                    role_id=role_id,
                    expected_keywords=expected_keywords,
                    expected_reference_doc_ids=expected_reference_doc_ids,
                )
                case_result["answer"] = asdict(answer_metrics)

            details.append(case_result)

    report = {
        "dataset_path": str(dataset_path),
        "knowledge_path": str(SETTINGS.knowledge_seed_path),
        "summary": summarize_report(details, args.mode),
        "details": details,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


class HttpClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.session.close()
        return False

    def reload_knowledge(self) -> None:
        response = self.session.post(f"{self.base_url}/knowledge/reload", timeout=120)
        response.raise_for_status()

    def create_user(self, user_id: str, name: str) -> None:
        response = self.session.post(
            f"{self.base_url}/users",
            json={"user_id": user_id, "name": name},
            timeout=60,
        )
        response.raise_for_status()

    def chat(
        self,
        *,
        session_id: str,
        user_id: str,
        role_id: str,
        message: str,
    ) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/chat",
            json={
                "session_id": session_id,
                "user_id": user_id,
                "role_id": role_id,
                "message": message,
            },
            timeout=180,
        )
        response.raise_for_status()
        return response.json()


class LocalClient:
    def __init__(self, test_client):
        self.test_client = test_client

    def __enter__(self) -> "LocalClient":
        self.test_client.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.test_client.__exit__(exc_type, exc, tb)
        return False

    def reload_knowledge(self) -> None:
        response = self.test_client.post("/knowledge/reload")
        response.raise_for_status()

    def create_user(self, user_id: str, name: str) -> None:
        response = self.test_client.post(
            "/users",
            json={"user_id": user_id, "name": name},
        )
        response.raise_for_status()

    def chat(
        self,
        *,
        session_id: str,
        user_id: str,
        role_id: str,
        message: str,
    ) -> dict[str, Any]:
        response = self.test_client.post(
            "/chat",
            json={
                "session_id": session_id,
                "user_id": user_id,
                "role_id": role_id,
                "message": message,
            },
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    main()
