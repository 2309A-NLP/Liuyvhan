"""
工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务
功能：从已有的 chunks 中调用 LLM 自动生成问答对，用于 Embedding 模型微调训练数据

用法：
  python scripts/generate_qa_pairs.py
  python scripts/generate_qa_pairs.py --force  # 重新生成全部

输出：
  data/processed/qa_pairs_generated.json  — LLM 生成的问答对
  data/processed/qa_pairs_merged.json     — 生成数据 + 人工标注数据合并
  data/processed/finetune_triplets.json   — 最终的三元组训练数据
"""

import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
EXPORTS_DIR = PROJECT_ROOT / "data" / "exports"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# 人工标注的黄金问答对
EVAL_QUESTIONS_FILE = PROCESSED_DIR / "evaluation_questions.json"

# 输出文件
GENERATED_QA_FILE = PROCESSED_DIR / "qa_pairs_generated.json"
MERGED_QA_FILE = PROCESSED_DIR / "qa_pairs_merged.json"
TRIPLETS_FILE = PROCESSED_DIR / "finetune_triplets.json"

# ── 配置 ──────────────────────────────────────────────────────
# 从 .env 读取或直接写在这里（生产环境建议用 env）
API_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1")
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V4-Flash")
TEMPERATURE = 0
MAX_CHUNKS_TO_PROCESS = 200  # 一次跑太多容易地址不够，先跑200条试水
BATCH_SIZE = 5              # 每批5个chunk，一次API调用出5个Q&A


def try_load_env():
    """尝试从 .env 加载环境变量"""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key == "LLM_BASE_URL" and not API_BASE_URL.startswith("http"):
                globals()["API_BASE_URL"] = val
            elif key == "LLM_API_KEY" and not API_KEY:
                globals()["API_KEY"] = val
            elif key == "LLM_MODEL":
                globals()["MODEL"] = val


def load_chunks() -> list[dict]:
    """加载所有 chunk 文件，返回合并后的列表"""
    chunks = []
    for f in sorted(PROCESSED_DIR.glob("*_chunks.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        print(f"  加载 {f.name}: {len(data)} chunks")
        chunks.extend(data)
    print(f"  总计: {len(chunks)} chunks")
    return chunks


def filter_chunks(chunks: list[dict]) -> list[dict]:
    """
    过滤合适的 chunk：
    - 只保留有实际文本内容的
    - 跳过太短的
    - 按页均匀采样，覆盖整份文档
    """
    valid = []
    for c in chunks:
        content = (c.get("content") or "").strip()
        if len(content) < 80:
            continue  # 太短，没有信息量
        valid.append(c)

    print(f"  有效chunks: {len(valid)}/{len(chunks)} (跳过{len(chunks)-len(valid)}个太短的)")

    # 按文档+页分组，每页最多取3个chunk
    page_groups = defaultdict(list)
    for c in valid:
        key = (c.get("file_name", "unknown"), c.get("page", 0))
        page_groups[key].append(c)

    sampled = []
    for key, group in page_groups.items():
        file_name, page = key
        # 同一页内按 block_type 优先选 content 最长的
        group.sort(key=lambda x: len(x.get("content", "")), reverse=True)
        sampled.extend(group[:3])

    # 最终打散一下顺序，不要全部是同一个文档的前面部分
    random.shuffle(sampled)
    print(f"  采样后: {len(sampled)} chunks (覆盖{len(page_groups)}页)")
    return sampled


def build_batch_prompt(chunks_batch: list[dict], batch_start_idx: int) -> str:
    """
    构造批量生成 Q&A 的 prompt。
    给 LLM 多个 chunk，让它在每个 chunk 的基础上生成一个问题+答案。
    """
    parts = []
    parts.append("你是一个专业的金融文档分析助手。请根据以下每个文本段落，分别生成一个中文问答对。")
    parts.append("要求：")
    parts.append("- 每个问题必须基于该段落的**具体事实**，不能泛泛而谈")
    parts.append("- 优先提关于：具体数字、金额、百分比、日期、人名、公司名、法律条款、业务描述等问题")
    parts.append("- 答案应直接从文本中提取，不要编造，不要添加外部知识")
    parts.append("- 问题要有一定难度，不能一眼就能回答（例如\"这是什么文件\"这种太简单的不算）")
    parts.append("- 每个段落生成 1 个问题")
    parts.append("")
    parts.append("请按以下 JSON 格式输出（只输出 JSON 数组，不要其他文字）：")
    parts.append("[")
    parts.append('  {"id": <序号>, "question": "问题", "reference_answer": "答案", "chunk_index": <对应段落序号>},')
    parts.append("  ...")
    parts.append("]")
    parts.append("")

    for i, chunk in enumerate(chunks_batch):
        content = chunk.get("content", "").strip()
        chunk_idx = batch_start_idx + i
        block_type = chunk.get("block_type", "page_text")
        page = chunk.get("page", "?")
        # 截断过长内容，避免超过上下文窗口
        if len(content) > 800:
            content = content[:800] + "…[截断]"
        parts.append(f"--- 段落 {chunk_idx} (第{page}页, {block_type}) ---")
        parts.append(content)
        parts.append("")

    return "\n".join(parts)


def parse_llm_response(raw_response: str, chunks_batch: list[dict], start_id: int, batch_start_idx: int) -> list[dict]:
    """解析 LLM 返回的 JSON，生成标准格式的问答对"""
    results = []

    # 尝试从 markdown 代码块中提取 JSON
    text = raw_response.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        pairs = json.loads(text)
    except json.JSONDecodeError:
        print(f"    [!] LLM 返回格式异常，尝试修复...")
        # 尝试找到最外层的 [ ]
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            text = text[start : end + 1]
            try:
                pairs = json.loads(text)
            except json.JSONDecodeError:
                print(f"    [x] 修复失败，丢弃此批")
                return results
        else:
            print(f"    [x] 找不到 JSON 数组，丢弃此批")
            return results

    for pair in pairs:
        chunk_idx = pair.get("chunk_index", batch_start_idx)
        pos_in_batch = chunk_idx - batch_start_idx
        if pos_in_batch < 0 or pos_in_batch >= len(chunks_batch):
            continue
        chunk = chunks_batch[pos_in_batch]
        results.append({
            "id": start_id + len(results),
            "question": pair.get("question", "").strip(),
            "reference_answer": pair.get("reference_answer", "").strip(),
            "chunk_id": chunk.get("chunk_id", ""),
            "chunk_content": chunk.get("content", ""),
            "page": chunk.get("page", 0),
            "file_name": chunk.get("file_name", ""),
            "block_type": chunk.get("block_type", "page_text"),
        })

    if results:
        print(f"    -> 成功解析 {len(results)}/{len(pairs)} 条")
    else:
        print(f"    [x] 解析出0条有效结果")
    return results


def generate_qa_pairs(chunks_to_process: list[dict], max_chunks: int = MAX_CHUNKS_TO_PROCESS) -> list[dict]:
    """调用 LLM 批量生成问答对"""
    from openai import OpenAI

    client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

    all_qa_pairs = []
    total = min(len(chunks_to_process), max_chunks)
    processed_count = 0
    global_id = 0

    print(f"\n开始生成 Q&A 对 (最多{total}个chunks, 每批{BATCH_SIZE}个)...")
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    for batch_start in range(0, total, BATCH_SIZE):
        batch = chunks_to_process[batch_start : batch_start + BATCH_SIZE]
        batch_idx = batch_start // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        prompt = build_batch_prompt(batch, batch_start)

        print(f"\n  批次 {batch_idx}/{total_batches} (chunk {batch_start}-{batch_start+len(batch)-1})...")

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的金融文档分析助手，输出严格遵循要求的 JSON 格式。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=4096,
                timeout=120,
            )
            raw = response.choices[0].message.content or ""
        except Exception as e:
            print(f"    [x] API 调用失败: {e}")
            # 等 3 秒后重试一次
            time.sleep(3)
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": "你是一个专业的金融文档分析助手，输出严格遵循要求的 JSON 格式。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=TEMPERATURE,
                    max_tokens=4096,
                    timeout=120,
                )
                raw = response.choices[0].message.content or ""
            except Exception as e2:
                print(f"    [x] 重试也失败: {e2}")
                continue

        qa_pairs = parse_llm_response(raw, batch, global_id + 1, batch_start)
        for qa in qa_pairs:
            qa["id"] = global_id + 1
            global_id += 1
        all_qa_pairs.extend(qa_pairs)
        processed_count += len(batch)

        # 保存中间结果，防止崩了丢失
        (GENERATED_QA_FILE.parent / "qa_pairs_temp.json").write_text(
            json.dumps(all_qa_pairs, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(f"  当前总计: {len(all_qa_pairs)} 条有效问答对 ({processed_count}/{total} chunks)")
        time.sleep(0.5)  # 避免 API 限流

    return all_qa_pairs


def load_existing_eval_questions() -> list[dict]:
    """加载人工标注的黄金问答对"""
    if EVAL_QUESTIONS_FILE.exists():
        data = json.loads(EVAL_QUESTIONS_FILE.read_text(encoding="utf-8"))
        print(f"  加载人工标注数据: {len(data)} 条")
        return data
    print("  未找到人工标注数据文件")
    return []


def build_triplets(merged_qa: list[dict], all_chunks: list[dict]) -> list[dict]:
    """
    从问答对构建三元组训练数据 (query, positive, negative)
    
    策略：
    - positive: 答案对应的原始 chunk
    - negative: 从不同文档/不同页随机选一个不相关的 chunk
    - 每个问答对生成 3 个三元组（3个不同的 negative）
    """
    # 建 chunk_id → chunk 索引
    chunk_map = {}
    for c in all_chunks:
        cid = c.get("chunk_id")
        if cid:
            chunk_map[cid] = c

    triplets = []
    skipped = 0

    for qa in merged_qa:
        chunk_id = qa.get("chunk_id", "")
        positive_chunk = chunk_map.get(chunk_id)
        if not positive_chunk:
            skipped += 1
            continue

        positive_content = positive_chunk.get("content", "").strip()
        if not positive_content:
            skipped += 1
            continue

        # 找 3 个不同的 negative
        negatives_used = set()
        for _ in range(3):
            candidates = [
                c for c in all_chunks
                if c.get("chunk_id") != chunk_id
                and c.get("file_name") != qa.get("file_name")  # 不同文档
                and c.get("content", "").strip()
                and len(c.get("content", "")) > 50
            ]
            # 如果不同文档不够，放宽到不同页
            if len(candidates) < 3:
                candidates = [
                    c for c in all_chunks
                    if c.get("chunk_id") != chunk_id
                    and c.get("page") != qa.get("page")
                    and c.get("content", "").strip()
                    and len(c.get("content", "")) > 50
                ]

            if not candidates:
                continue

            neg = random.choice(candidates)
            neg_cid = neg.get("chunk_id", "")
            if neg_cid in negatives_used:
                continue
            negatives_used.add(neg_cid)

            triplets.append({
                "query": qa["question"],
                "positive": positive_content,
                "negative": neg.get("content", "").strip(),
                "positive_chunk_id": chunk_id,
                "negative_chunk_id": neg_cid,
                "file_name": qa.get("file_name", ""),
                "source": "synthetic" if qa.get("chunk_id") else "manual",
            })

    print(f"  三元组生成: {len(triplets)} 条 (跳过 {skipped} 条无法匹配的)")
    return triplets


def main():
    parser = argparse.ArgumentParser(description="生成 Embedding 微调训练数据")
    parser.add_argument("--force", action="store_true", help="强制重新生成全部")
    parser.add_argument("--limit", type=int, default=MAX_CHUNKS_TO_PROCESS, help=f"最多处理chunks数 (默认{MAX_CHUNKS_TO_PROCESS})")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help=f"每批chunks数 (默认{BATCH_SIZE})")
    args = parser.parse_args()

    try_load_env()

    print("=" * 60)
    print("Embedding 微调 - 训练数据生成器")
    print("=" * 60)

    # 1. 加载所有 chunks
    print("\n[1/4] 加载 chunks...")
    all_chunks = load_chunks()

    # 2. 过滤 + 采样
    print("\n[2/4] 过滤和采样 chunks...")
    sampled_chunks = filter_chunks(all_chunks)

    # 3. 生成问答对（如果已有且不强制则跳过）
    print("\n[3/4] 生成问答对...")
    if GENERATED_QA_FILE.exists() and not args.force:
        print(f"  已有生成数据文件: {GENERATED_QA_FILE.name}")
        qa_generated = json.loads(GENERATED_QA_FILE.read_text(encoding="utf-8"))
        print(f"  加载 {len(qa_generated)} 条")
    else:
        qa_generated = generate_qa_pairs(sampled_chunks, max_chunks=args.limit)
        GENERATED_QA_FILE.write_text(
            json.dumps(qa_generated, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n  已保存: {GENERATED_QA_FILE.name} ({len(qa_generated)} 条)")

    # 4. 合并人工数据 + 生成数据
    print("\n[4/4] 合并数据并构建三元组...")
    manual_qa = load_existing_eval_questions()
    all_qa = manual_qa + qa_generated
    print(f"  合并后总计: {len(all_qa)} 条问答对")

    # 去重（以 question 为 key）
    seen_questions = set()
    deduped_qa = []
    for qa in all_qa:
        q = qa.get("question", "").strip()
        if q and q not in seen_questions:
            seen_questions.add(q)
            deduped_qa.append(qa)
    print(f"  去重后: {len(deduped_qa)} 条")

    MERGED_QA_FILE.write_text(
        json.dumps(deduped_qa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  已保存合并数据: {MERGED_QA_FILE.name}")

    # 5. 构建三元组
    triplets = build_triplets(deduped_qa, all_chunks)
    TRIPLETS_FILE.write_text(
        json.dumps(triplets, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  已保存三元组: {TRIPLETS_FILE.name} ({len(triplets)} 条)")

    # 清理临时文件
    temp_file = GENERATED_QA_FILE.parent / "qa_pairs_temp.json"
    if temp_file.exists():
        temp_file.unlink()

    print("\n" + "=" * 60)
    print("完成!")
    print(f"  生成问答对: {len(qa_generated)} 条")
    print(f"  人工标注:   {len(manual_qa)} 条")
    print(f"  合并去重后: {len(deduped_qa)} 条")
    print(f"  三元组:     {len(triplets)} 条")
    print(f"\n  下一步: 运行微调脚本 finetune_embedding.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
