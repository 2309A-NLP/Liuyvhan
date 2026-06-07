import json
from pathlib import Path

import pandas as pd
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from ragas import EvaluationDataset, evaluate
from ragas.llms import LangchainLLMWrapper

from app.core.config import settings

try:
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
except ImportError:
    answer_relevancy = None
    context_precision = None
    context_recall = None
    faithfulness = None


class EvaluationService:
    def __init__(self, rag_service, llm_service) -> None:
        self.rag_service = rag_service
        self.llm_service = llm_service

    def run(self, questions_file: str, file_name: str | None = None, top_k: int | None = None) -> dict:
        questions_path = Path(questions_file)
        questions = json.loads(questions_path.read_text(encoding="utf-8"))

        rows: list[dict] = []
        ragas_records: list[dict] = []

        for item in questions:
            rag_response = self.rag_service.ask_rag(
                question=item["question"],
                file_name=file_name,
                top_k=top_k,
                force_refresh=True,
            )
            llm_response = self.rag_service.ask_llm(
                question=item["question"],
                force_refresh=True,
            )

            rows.append(
                {
                    "id": item["id"],
                    "question": item["question"],
                    "reference_answer": item["reference_answer"],
                    "rag_answer": rag_response["answer"],
                    "llm_answer": llm_response["answer"],
                    "rag_sources": rag_response["sources"],
                    "rag_latency_seconds": rag_response["latency_seconds"],
                    "llm_latency_seconds": llm_response["latency_seconds"],
                }
            )

            ragas_records.append(
                {
                    "user_input": item["question"],
                    "reference": item["reference_answer"],
                    "response": rag_response["answer"],
                    "retrieved_contexts": [source["content"] for source in rag_response["sources"]],
                }
            )

        ragas_error: str | None = None
        try:
            ragas_result = self._run_ragas(ragas_records)
        except Exception as exc:
            ragas_result = {}
            ragas_error = str(exc)

        result_df = pd.DataFrame(rows)
        metrics_df = pd.DataFrame([ragas_result]) if ragas_result else pd.DataFrame()
        export_df = result_df.copy()
        export_df = export_df.rename(
            columns={
                "id": "题号",
                "question": "问题",
                "reference_answer": "标准答案",
                "rag_answer": "RAG答案",
                "llm_answer": "纯LLM答案",
                "rag_sources": "RAG来源",
                "rag_latency_seconds": "RAG耗时(秒)",
                "llm_latency_seconds": "纯LLM耗时(秒)",
            }
        )

        display_metric_map = {
            "answer_relevancy": "答案相关性",
            "context_precision": "上下文精确率",
            "context_recall": "上下文召回率",
            "faithfulness": "忠实度",
        }
        for key, value in ragas_result.items():
            export_df[display_metric_map.get(key, key)] = value

        csv_path = Path(settings.eval_output_csv).resolve()
        json_path = Path(settings.eval_output_json).resolve()
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        export_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        json_path.write_text(
            json.dumps(
                {
                    "总题数": len(rows),
                    "RAGAS指标": {
                        display_metric_map.get(key, key): value for key, value in ragas_result.items()
                    },
                    "RAGAS错误": ragas_error,
                    "字段说明": {
                        "题号": "问题编号",
                        "问题": "用户提问",
                        "标准答案": "人工标注参考答案",
                        "RAG答案": "检索增强问答结果",
                        "纯LLM答案": "不检索文档时的大模型回答",
                        "RAG来源": "检索到的上下文片段",
                        "RAG耗时(秒)": "RAG链路单题耗时",
                        "纯LLM耗时(秒)": "纯LLM链路单题耗时",
                        "答案相关性": "RAGAS answer_relevancy",
                        "上下文精确率": "RAGAS context_precision",
                        "上下文召回率": "RAGAS context_recall",
                        "忠实度": "RAGAS faithfulness",
                    },
                    "记录": [
                        {
                            "题号": row["id"],
                            "问题": row["question"],
                            "标准答案": row["reference_answer"],
                            "RAG答案": row["rag_answer"],
                            "纯LLM答案": row["llm_answer"],
                            "RAG来源": row["rag_sources"],
                            "RAG耗时(秒)": row["rag_latency_seconds"],
                            "纯LLM耗时(秒)": row["llm_latency_seconds"],
                        }
                        for row in rows
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return {
            "total_questions": len(rows),
            "ragas_metrics": ragas_result,
            "csv_path": str(csv_path),
            "json_path": str(json_path),
            "records": rows,
            "metrics_table": metrics_df.to_dict(orient="records")[0] if not metrics_df.empty else {},
            "ragas_error": ragas_error,
        }

    def _run_ragas(self, ragas_records: list[dict]) -> dict[str, float]:
        dataset = EvaluationDataset.from_list(ragas_records)
        langchain_llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=0,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        evaluator_llm = LangchainLLMWrapper(langchain_llm)
        evaluator_embeddings = self._build_ragas_embeddings()

        metrics = None
        if all(metric is not None for metric in [answer_relevancy, context_precision, context_recall, faithfulness]):
            metrics = [answer_relevancy, context_precision, context_recall, faithfulness]

        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
            raise_exceptions=False,
            show_progress=False,
        )

        if hasattr(result, "to_pandas"):
            dataframe = result.to_pandas()
            numeric_cols = dataframe.select_dtypes(include=["number"]).columns.tolist()
            return {column: round(float(dataframe[column].mean()), 4) for column in numeric_cols}

        result_dict = dict(result)
        return {key: round(float(value), 4) for key, value in result_dict.items() if isinstance(value, (int, float))}

    def _build_ragas_embeddings(self) -> HuggingFaceEmbeddings:
        local_model_path = Path(settings.embedding_model_path.strip()) if settings.embedding_model_path.strip() else None
        has_local_model = bool(local_model_path and local_model_path.exists())
        model_name = str(local_model_path) if has_local_model else settings.embedding_model
        return HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"local_files_only": has_local_model},
            encode_kwargs={"normalize_embeddings": True},
        )
