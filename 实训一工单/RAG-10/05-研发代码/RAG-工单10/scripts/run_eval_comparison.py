"""
工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务
功能：运行微调前 / 微调后 RAGAS 评估对比，生成对比报告

用法：
  # 微调前评估（基线）
  python scripts/run_eval_comparison.py --baseline

  # 微调后评估（先修改 .env 的 EMBEDDING_MODEL_PATH，然后）
  # 然后重新启动服务，重新索引PDF
  python scripts/run_eval_comparison.py --after

  # 生成对比报告
  python scripts/run_eval_comparison.py --report

输出：
  data/exports/eval_baseline/       — 微调前评估结果
  data/exports/eval_after_finetune/ — 微调后评估结果
  data/exports/eval_comparison.md   — 对比报告
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORTS_DIR = PROJECT_ROOT / "data" / "exports"
BASELINE_DIR = EXPORTS_DIR / "eval_baseline"
AFTER_DIR = EXPORTS_DIR / "eval_after_finetune"
COMPARISON_FILE = EXPORTS_DIR / "eval_comparison.md"


def run_evaluation(output_dir: Path) -> dict:
    """运行 RAGAS 评估并保存结果"""
    # 动态导入，确保服务已启动
    sys.path.insert(0, str(PROJECT_ROOT))

    from app.core.container import container

    print(f"\n运行评估...")
    result = container.evaluation_service.run(
        questions_file=str(PROJECT_ROOT / "data" / "processed" / "evaluation_questions.json"),
        file_name=None,
        top_k=None,
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存评估结果
    summary_path = output_dir / "ragas_eval_summary.json"
    json.dump(result, open(summary_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"  评估结果已保存: {summary_path}")

    # 复制 CSV
    csv_path = PROJECT_ROOT / "data" / "exports" / "ragas_eval_results.csv"
    if csv_path.exists():
        shutil.copy2(csv_path, output_dir / "ragas_eval_results.csv")

    return result


def generate_comparison_report(baseline: dict, after: dict):
    """生成微调前后对比报告"""
    baseline_metrics = baseline.get("ragas_metrics", {})
    after_metrics = after.get("ragas_metrics", {})

    COMPARISON_FILE.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# Embedding 模型微调前后评估对比报告")
    lines.append("")
    lines.append(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(f"工单编号: 人工智能NLP-RAG项目-11-Embeddings模型微调任务")
    lines.append("")
    lines.append("## 基本信息")
    lines.append("")
    lines.append(f"- 评估问题数量: {baseline.get('total_questions', '?')} 题")
    lines.append(f"- 基准模型: baseline 对应微调前模型, after 对应微调后模型")
    lines.append("")
    lines.append("## RAGAS 指标对比")
    lines.append("")
    lines.append("| 指标 | 微调前 (Baseline) | 微调后 (After) | 变化 | 说明 |")
    lines.append("|------|-----------------|----------------|------|------|")

    metric_descriptions = {
        "context_precision": "上下文精确率 — 检索结果中有多少是真正相关的",
        "context_recall": "上下文召回率 — 所有真正相关的文档被检索到了多少",
        "faithfulness": "忠实度 — 生成答案是否忠实于检索到的上下文",
        "answer_relevancy": "答案相关性 — 答案与问题的匹配程度",
    }

    all_metrics = set(list(baseline_metrics.keys()) + list(after_metrics.keys()))
    for metric in sorted(all_metrics):
        base_val = baseline_metrics.get(metric, "N/A")
        after_val = after_metrics.get(metric, "N/A")
        desc = metric_descriptions.get(metric, "")

        if isinstance(base_val, (int, float)) and isinstance(after_val, (int, float)):
            diff = after_val - base_val
            diff_str = f"{diff:+.4f}"
            if diff > 0:
                diff_str += " ↑"
            elif diff < 0:
                diff_str += " ↓"
            else:
                diff_str += " —"
            lines.append(f"| {metric} | {base_val:.4f} | {after_val:.4f} | {diff_str} | {desc} |")
        else:
            lines.append(f"| {metric} | {base_val} | {after_val} | — | {desc} |")

    lines.append("")
    lines.append("## 结论")
    lines.append("")

    # 自动判断是否通过验收
    improved = 0
    degraded = 0
    for metric in all_metrics:
        base_val = baseline_metrics.get(metric)
        after_val = after_metrics.get(metric)
        if isinstance(base_val, (int, float)) and isinstance(after_val, (int, float)):
            if after_val > base_val:
                improved += 1
            elif after_val < base_val:
                degraded += 1

    total = improved + degraded
    if total > 0 and improved >= total * 0.5:
        lines.append(f"✅ **验收结论：通过** — {total}个可评估指标中，{improved}个提升，{degraded}个下降。")
    elif total > 0:
        lines.append(f"⚠️ **验收结论：未通过** — {total}个可评估指标中，仅{improved}个提升，{degraded}个下降。")
    else:
        lines.append("⚠️ **验收结论：数据不足** — 无法得出明确结论。")
    lines.append("")
    lines.append(f"> (说明: 大于50%的指标提升即认为微调有效)")
    lines.append("")

    COMPARISON_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n对比报告已生成: {COMPARISON_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Embedding 模型微调前后评估对比")
    parser.add_argument("--baseline", action="store_true", help="运行微调前评估（基线）")
    parser.add_argument("--after", action="store_true", help="运行微调后评估")
    parser.add_argument("--report", action="store_true", help="生成对比报告（基于已有数据）")
    args = parser.parse_args()

    if args.baseline:
        print("=" * 60)
        print("  微调前评估 (Baseline)")
        print("  请确认当前 .env 的 EMBEDDING_MODEL_PATH 指向的是原 m3e-base 模型")
        print("=" * 60)
        result = run_evaluation(BASELINE_DIR)
        print(f"\n基线评估完成!")
        print(f"  RAGAS指标: {result.get('ragas_metrics', {})}")

    elif args.after:
        print("=" * 60)
        print("  微调后评估 (After Finetune)")
        print("  请确认:")
        print("  1. 已修改 .env 的 EMBEDDING_MODEL_PATH 指向 data/models/finetuned-bge-zh/")
        print("  2. 已重启服务")
        print("  3. 已重新索引所有PDF")
        print("=" * 60)
        confirm = input("\n确认以上都已完成？(y/n): ")
        if confirm.lower() != "y":
            print("取消评估")
            return
        result = run_evaluation(AFTER_DIR)
        print(f"\n微调后评估完成!")
        print(f"  RAGAS指标: {result.get('ragas_metrics', {})}")

        # 自动生成对比报告
        if BASELINE_DIR.exists():
            print("\n发现基线数据，自动生成对比报告...")
            baseline_result = json.load(open(BASELINE_DIR / "ragas_eval_summary.json", encoding="utf-8"))
            generate_comparison_report(baseline_result, result)

    elif args.report:
        print("=" * 60)
        print("  生成对比报告")
        print("=" * 60)

        if not BASELINE_DIR.exists():
            print("[错误] 找不到基线数据，请先运行 --baseline")
            sys.exit(1)
        if not AFTER_DIR.exists():
            print("[错误] 找不到微调后数据，请先运行 --after")
            sys.exit(1)

        baseline_result = json.load(open(BASELINE_DIR / "ragas_eval_summary.json", encoding="utf-8"))
        after_result = json.load(open(AFTER_DIR / "ragas_eval_summary.json", encoding="utf-8"))
        generate_comparison_report(baseline_result, after_result)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
