"""
工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务
功能：基于 BAAI/bge-base-zh-v1.5 在金融文档数据上微调 Embedding 模型

用法：
  python scripts/finetune_embedding.py
  python scripts/finetune_embedding.py --epochs 5 --batch-size 16

输出：
  data/models/finetuned-bge-zh/  — 微调后的模型权重
  data/exports/finetune_report.txt  — 训练报告
  data/exports/finetune_loss_curve.png  — 损失曲线图
"""

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
EXPORTS_DIR = PROJECT_ROOT / "data" / "exports"
MODELS_DIR = PROJECT_ROOT / "data" / "models"

TRIPLETS_FILE = PROCESSED_DIR / "finetune_triplets.json"
MODEL_OUTPUT_DIR = MODELS_DIR / "finetuned-bge-zh"

# 临时禁用离线模式（需要联网下载 bge-base-zh-v1.5）
os.environ["HF_HUB_OFFLINE"] = "0"
os.environ["TRANSFORMERS_OFFLINE"] = "0"

# 基准模型（BGE 中文版，768维，适合金融中文）
BASE_MODEL_NAME = "BAAI/bge-base-zh-v1.5"


def check_environment():
    """检查依赖是否安装"""
    missing = []
    try:
        import sentence_transformers
        print(f"  sentence-transformers: {sentence_transformers.__version__}")
    except ImportError:
        missing.append("sentence-transformers")

    try:
        import torch
        print(f"  torch: {torch.__version__} (CUDA可用: {torch.cuda.is_available()})")
        if torch.cuda.is_available():
            print(f"    GPU: {torch.cuda.get_device_name(0)}")
        else:
            print("    [CPU模式] 训练将在 CPU 上进行，速度较慢但数据量小没问题")
    except ImportError:
        missing.append("torch")

    try:
        import datasets
        print(f"  datasets: {datasets.__version__}")
    except ImportError:
        missing.append("datasets")

    try:
        import matplotlib
        matplotlib.use("Agg")  # 无头模式
        print(f"  matplotlib: {matplotlib.__version__}")
    except ImportError:
        missing.append("matplotlib")

    if missing:
        print(f"\n[错误] 缺少依赖: {', '.join(missing)}")
        print("请运行: pip install sentence-transformers torch datasets matplotlib")
        sys.exit(1)


def load_triplets() -> list[dict]:
    """加载三元组训练数据"""
    if not TRIPLETS_FILE.exists():
        print(f"\n[错误] 找不到三元组数据文件: {TRIPLETS_FILE}")
        print("请先运行 python scripts/generate_qa_pairs.py")
        sys.exit(1)

    triplets = json.loads(TRIPLETS_FILE.read_text(encoding="utf-8"))
    print(f"  加载 {len(triplets)} 条三元组")

    # 统计来源
    synthetic = sum(1 for t in triplets if t.get("source") == "synthetic")
    manual = sum(1 for t in triplets if t.get("source") == "manual")
    print(f"    人工标注来源: {manual} 条")
    print(f"    合成数据来源: {synthetic} 条")

    # 统计 unique queries
    unique_queries = len(set(t["query"] for t in triplets))
    print(f"    唯一问题数: {unique_queries}")

    return triplets


def build_training_data(triplets: list[dict]):
    """
    将三元组转换为 SentenceTransformers 可用的格式。
    使用 InputExample 构造 (anchor, positive, negative) 三元组。
    """
    from sentence_transformers import InputExample

    examples = []
    for t in triplets:
        examples.append(InputExample(
            texts=[t["query"], t["positive"], t["negative"]]
        ))

    # 打乱
    import random
    random.shuffle(examples)

    print(f"  构造 {len(examples)} 个训练样本 (InputExample)")
    return examples


def train_model(
    train_examples,
    base_model_name: str = BASE_MODEL_NAME,
    output_dir: Path = MODEL_OUTPUT_DIR,
    num_epochs: int = 3,
    batch_size: int = 8,
    warmup_steps: int = 0,
    learning_rate: float = 2e-5,
    eval_split_ratio: float = 0.1,
):
    """
    使用 TripletLoss 训练 Embedding 模型

    Args:
        train_examples: List[InputExample]
        base_model_name: HuggingFace 模型名
        output_dir: 模型保存路径
        num_epochs: 训练轮数
        batch_size: 批次大小
        warmup_steps: 预热步数
        learning_rate: 学习率
        eval_split_ratio: 验证集比例
    """
    from sentence_transformers import SentenceTransformer, SentencesDataset, losses
    from sentence_transformers.evaluation import EmbeddingSimilarityEvaluator, TripletEvaluator
    from torch.utils.data import DataLoader

    print(f"\n{'='*60}")
    print("开始微调 Embedding 模型")
    print(f"  基准模型: {base_model_name}")
    print(f"  训练样本: {len(train_examples)}")
    print(f"  轮数: {num_epochs}")
    print(f"  Batch Size: {batch_size}")
    print(f"  学习率: {learning_rate}")
    print(f"  输出目录: {output_dir}")
    print(f"{'='*60}")

    # 1. 加载基准模型
    print("\n[1/5] 加载基准模型...")
    print(f"  正在从 HuggingFace 下载: {base_model_name}")
    model = SentenceTransformer(base_model_name)
    embedding_dim = model.get_sentence_embedding_dimension()
    print(f"  模型维度: {embedding_dim}")
    print(f"  最大序列长度: {model.max_seq_length}")

    # 2. 准备数据加载器
    print(f"\n[2/5] 准备数据...")

    # 划分训练/验证集
    split_idx = int(len(train_examples) * (1 - eval_split_ratio))
    train_data = train_examples[:split_idx]
    eval_data = train_examples[split_idx:]
    print(f"  训练集: {len(train_data)} 条")
    print(f"  验证集: {len(eval_data)} 条")

    train_dataloader = DataLoader(train_data, shuffle=True, batch_size=batch_size)

    # 3. 定义损失函数 — 使用 TripletLoss
    print(f"\n[3/5] 配置损失函数...")
    train_loss = losses.TripletLoss(model=model)
    print(f"  损失函数: TripletLoss (距离度量: cosine)")

    # 4. 配置训练参数
    print(f"\n[4/5] 配置训练参数...")
    num_steps = math.ceil(len(train_data) / batch_size) * num_epochs
    if warmup_steps <= 0:
        warmup_steps = int(num_steps * 0.1)  # 默认10%预热
    print(f"  总步数: {num_steps}")
    print(f"  预热步数: {warmup_steps}")

    # 5. 训练
    print(f"\n[5/5] 开始训练...")
    print(f"  (CPU模式，预计 {len(train_data)//batch_size * num_epochs * 2} 秒完成)")
    print()

    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=num_epochs,
        warmup_steps=warmup_steps,
        optimizer_params={"lr": learning_rate},
        output_path=str(output_dir),
        save_best_model=True,
        show_progress_bar=True,
        use_amp=False,  # CPU 不需要 AMP
        checkpoint_path=str(output_dir / "checkpoints"),
        checkpoint_save_steps=max(1, num_steps // 3),  # 每三分之一步保存一次
    )

    print(f"\n  模型已保存至: {output_dir}")
    return model


def evaluate_model(model, test_queries: list[str], test_positives: list[str], test_negatives: list[str]):
    """快速评估模型在测试数据上的表现"""
    from sklearn.metrics import accuracy_score

    print(f"\n快速评估 (余弦相似度)")

    pos_scores = []
    neg_scores = []

    for q, p, n in zip(test_queries, test_positives, test_negatives):
        emb_q = model.encode(q, normalize_embeddings=True)
        emb_p = model.encode(p, normalize_embeddings=True)
        emb_n = model.encode(n, normalize_embeddings=True)

        import numpy as np
        pos_sim = float(np.dot(emb_q, emb_p))
        neg_sim = float(np.dot(emb_q, emb_n))

        pos_scores.append(pos_sim)
        neg_scores.append(neg_sim)

    correct = sum(1 for p, n in zip(pos_scores, neg_scores) if p > n)
    total = len(pos_scores)
    accuracy = correct / total if total > 0 else 0

    import numpy as np
    avg_pos = np.mean(pos_scores)
    avg_neg = np.mean(pos_scores)

    print(f"  测试样本数: {total}")
    print(f"  正例平均相似度: {avg_pos:.4f}")
    print(f"  负例平均相似度: {avg_neg:.4f}")
    print(f"  排序准确率 (正例>负例): {accuracy:.2%} ({correct}/{total})")

    return {
        "accuracy": accuracy,
        "avg_pos_similarity": float(avg_pos),
        "avg_neg_similarity": float(avg_neg),
        "total": total,
        "correct": correct,
    }


def save_training_report(triplets_count, eval_results, num_epochs, batch_size, learning_rate, duration_seconds, output_dir):
    """保存训练报告"""
    report_path = EXPORTS_DIR / "finetune_report.txt"
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report = f"""
Embedding 模型微调训练报告
{'='*60}

基本信息
  工单编号: 人工智能NLP-RAG项目-11-Embeddings模型微调任务
  任务日期: {time.strftime('%Y-%m-%d %H:%M:%S')}
  基准模型: {BASE_MODEL_NAME}
  输出路径: {output_dir}

训练参数
  训练三元组: {triplets_count} 条
  训练轮数: {num_epochs}
  Batch Size: {batch_size}
  学习率: {learning_rate}
  损失函数: TripletLoss

训练耗时
  {duration_seconds:.1f} 秒 ({duration_seconds/60:.1f} 分钟)

快速评估（余弦相似度排序准确率）
  准确率: {eval_results.get('accuracy', 'N/A'):.2%}
  正例平均相似度: {eval_results.get('avg_pos_similarity', 'N/A'):.4f}
  负例平均相似度: {eval_results.get('avg_neg_similarity', 'N/A'):.4f}
"""
    report_path.write_text(report.strip(), encoding="utf-8")
    print(f"\n训练报告已保存: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Embedding 模型微调训练")
    parser.add_argument("--epochs", type=int, default=3, help="训练轮数 (默认3)")
    parser.add_argument("--batch-size", type=int, default=8, help="批次大小 (默认8, CPU建议4-8)")
    parser.add_argument("--lr", type=float, default=2e-5, help="学习率 (默认2e-5)")
    parser.add_argument("--model", type=str, default=BASE_MODEL_NAME, help="基准模型名称")
    parser.add_argument("--test-only", action="store_true", help="只做快速测试，不训练")
    args = parser.parse_args()

    print("=" * 60)
    print("Embedding 模型微调训练器")
    print("=" * 60)

    # 检查环境
    print("\n[环境检查]")
    check_environment()

    # 加载数据
    print("\n[加载数据]")
    triplets = load_triplets()
    if len(triplets) == 0:
        print("[错误] 三元组数据为空！")
        sys.exit(1)

    # 构建训练数据
    print("\n[构建训练数据]")
    train_examples = build_training_data(triplets)

    if args.test_only:
        print("\n[测试模式] 不进行训练，仅检查数据")
        print(f"  训练样本数: {len(train_examples)}")
        print(f"  三元组数据: {len(triplets)} 条")
        print(f"  唯一问题: {len(set(t['query'] for t in triplets))}")
        sys.exit(0)

    # 开始训练
    start_time = time.time()
    model = train_model(
        train_examples,
        base_model_name=args.model,
        output_dir=MODEL_OUTPUT_DIR,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
    )
    duration = time.time() - start_time

    # 快速评估
    print("\n[模型评估]")
    # 从训练数据中取最后 20 条作为测试
    test_triplets = triplets[-min(20, len(triplets)):]
    test_queries = [t["query"] for t in test_triplets]
    test_positives = [t["positive"] for t in test_triplets]
    test_negatives = [t["negative"] for t in test_triplets]
    eval_results = evaluate_model(model, test_queries, test_positives, test_negatives)

    # 保存报告
    save_training_report(
        triplets_count=len(triplets),
        eval_results=eval_results,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        duration_seconds=duration,
        output_dir=MODEL_OUTPUT_DIR,
    )

    print("\n" + "=" * 60)
    print("微调完成！")
    print(f"  模型路径: {MODEL_OUTPUT_DIR}")
    print(f"  训练耗时: {duration:.1f} 秒")
    print(f"  排序准确率: {eval_results.get('accuracy', 'N/A'):.2%}")
    print()
    print("接下来:")
    print("  1. 修改 .env 配置: EMBEDDING_MODEL_PATH=data/models/finetuned-bge-zh/")
    print("  2. 重启服务，重新索引所有PDF")
    print("  3. 运行评估对比: python scripts/run_evaluation.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
