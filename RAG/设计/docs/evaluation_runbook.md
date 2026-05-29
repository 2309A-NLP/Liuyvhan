# Evaluation Runbook

## Goal

Use `evaluation/ragas_eval.py` to separate three questions:

- Did retrieval return the right chunks?
- Did the final answer cite the right chunks?
- Did the final answer cover the expected keywords?

## How To Run

Run the full layered evaluation:

```powershell
python evaluation/ragas_eval.py --mode all --reload-knowledge
```

Run retrieval only:

```powershell
python evaluation/ragas_eval.py --mode retrieval --reload-knowledge
```

Run final answer only:

```powershell
python evaluation/ragas_eval.py --mode chat --reload-knowledge
```

Use a custom dataset:

```powershell
python evaluation/ragas_eval.py --mode all --dataset data/seed/eval_dataset.json
```

## Dataset Fields

Current dataset fields already supported:

- `question`
- `role_id`
- `expected_keywords`

Optional fields for stronger evaluation:

- `expected_doc_ids`
- `expected_reference_doc_ids`

If `expected_doc_ids` is missing, the script will try to infer relevant documents from
`knowledge_documents.json` using `expected_keywords`. That is useful for bootstrap evaluation,
but explicit doc ids are more trustworthy.

## How To Read The Report

Most useful summary fields:

- `retrieval.average_recall`: whether the retriever can bring back expected chunks.
- `retrieval.average_mrr`: whether a relevant chunk appears near the top.
- `answer.average_reference_recall`: whether the final response cites expected chunks.
- `answer.average_keyword_hit_rate`: whether the final answer covers target concepts.

Typical diagnosis patterns:

- Retrieval recall low, answer keyword hit also low: recall is the main problem.
- Retrieval recall high, reference recall low: generation is not using retrieved context well.
- Retrieval recall high, reference recall high, keyword hit low: prompts or answer shaping need work.

## Recommended Next Step

For serious benchmarking, add `expected_doc_ids` to every evaluation case. That turns the script
from a useful bootstrap evaluator into a much more reliable regression tool.
