import base64
import json
from collections import defaultdict
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from PIL import Image

from app.core.config import settings
from app.core.container import container


debug_router = APIRouter()


def _find_doc_id(file_name: str) -> str | None:
    """从 manifest 文件查找 doc_id，选 chunks 数最多的版本"""
    candidates = []
    for mf in settings.processed_dir.glob("*_manifest.json"):
        try:
            manifest = json.loads(mf.read_text(encoding="utf-8"))
            if manifest.get("file_name") == file_name:
                candidates.append(manifest)
        except Exception:
            continue
    if not candidates:
        return None
    # 选 chunks 最多的版本（通常是带 VLM 的增强版）
    candidates.sort(key=lambda m: m.get("chunks", 0), reverse=True)
    return candidates[0].get("doc_id")


def _load_chunks_from_disk(file_name: str) -> list[dict] | None:
    """从磁盘加载已处理好的 chunks"""
    doc_id = _find_doc_id(file_name)
    if not doc_id:
        return None
    chunks_path = settings.processed_dir / f"{doc_id}_chunks.json"
    if not chunks_path.exists():
        return None
    try:
        return json.loads(chunks_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_image_preview(doc_id: str, page: int, image_index: int) -> str:
    """加载已保存的图片缩略图（base64）"""
    img_dir = settings.image_dir / doc_id
    candidates = [
        img_dir / f"page_{page:04d}_image_{image_index:02d}.png",
    ]
    for path in candidates:
        if path.exists():
            try:
                img = Image.open(path)
                img.thumbnail((200, 200))
                buf = BytesIO()
                img.save(buf, format="PNG")
                return base64.b64encode(buf.getvalue()).decode()
            except Exception:
                return ""
    return ""


def _reconstruct_pages_from_chunks(chunks: list[dict], max_pages: int = 5) -> list[dict]:
    """从 chunks 反向重建分页数据"""
    pages_dict: dict[int, dict] = {}

    for chunk in chunks:
        p = chunk["page"]
        if p > max_pages:
            continue
        if p not in pages_dict:
            pages_dict[p] = {
                "page": p,
                "text_chunks": [],
                "table_chunks": [],
                "image_chunks": [],
                "chunk_count": 0,
            }
        bt = chunk.get("block_type", "page_text")
        if bt == "image":
            pages_dict[p]["image_chunks"].append(chunk)
        elif bt == "table":
            pages_dict[p]["table_chunks"].append(chunk)
        else:
            pages_dict[p]["text_chunks"].append(chunk)
        pages_dict[p]["chunk_count"] += 1

    doc_id = chunks[0].get("doc_id", "") if chunks else ""

    result = []
    for p in sorted(pages_dict.keys()):
        pd = pages_dict[p]

        # 文本：合并 page_text block 的 content
        raw_text = "\n".join(
            c["content"] for c in pd["text_chunks"]
        )[:2000]

        # 表格内容
        table_blocks = [
            {"index": i, "content": c["content"][:800]}
            for i, c in enumerate(pd["table_chunks"][:5])
        ]

        # 图片预览
        image_previews = []
        for c in pd["image_chunks"][:5]:
            # 获取图片文件名
            image_path = c.get("image_path", "")
            # 尝试解析图片索引
            import re
            m = re.search(r"image_(\d+)", image_path)
            img_idx = int(m.group(1)) if m else 1

            preview_b64 = _load_image_preview(doc_id, p, img_idx)

            # 从 content 解析 CLIP 和 VLM
            content = c["content"]
            clip_labels = []
            vlm_desc = ""
            # 从 content 正则提取 CLIP 标签
            clip_m = re.search(r"CLIP语义标签:\s*(.+)", content)
            if clip_m:
                parts = clip_m.group(1).split("，")
                for part in parts[:3]:
                    m2 = re.match(r"(.+)\((\d+\.\d+)\)", part.strip())
                    if m2:
                        clip_labels.append({"label": m2.group(1), "score": float(m2.group(2))})

            # 提取 VLM 描述
            vlm_m = re.search(r"多模态描述:\s*(.+)", content)
            if vlm_m:
                vlm_desc = vlm_m.group(1).strip()

            image_previews.append({
                "path": image_path,
                "thumbnail_b64": preview_b64,
                "clip_labels": clip_labels,
                "vlm_description": vlm_desc,
                "content": content,
                "block_index": img_idx,
            })

        result.append({
            "page": p,
            "raw_text": raw_text,
            "text_blocks": [{"index": 0, "content": raw_text[:800]}] if raw_text else [],
            "table_blocks": table_blocks,
            "image_previews": image_previews,
        })

    return result


@debug_router.get("/debug/preview")
async def debug_preview(
    file_name: str = Query(default="招股说明书1.pdf"),
    max_pages: int = Query(default=5, description="最多显示页数"),
):
    """返回 PDF 各阶段处理结果，从磁盘已处理数据快速读取"""
    chunks = _load_chunks_from_disk(file_name)
    if chunks is None:
        raise HTTPException(
            status_code=404,
            detail=f"未找到 {file_name} 的处理结果。请先建立索引（POST /api/v1/documents/index）。",
        )

    doc_id = chunks[0].get("doc_id", "") if chunks else ""
    total_chunks = len(chunks)

    # 统计 chunk 类型
    chunk_types = defaultdict(int)
    for c in chunks:
        chunk_types[c.get("block_type", "page_text")] += 1

    # 获取所有页数
    all_pages = sorted(set(c["page"] for c in chunks))
    total_pages = max(all_pages) if all_pages else 0

    # 重建页面数据
    pages_data = _reconstruct_pages_from_chunks(chunks, max_pages=max_pages)

    # 前 20 个 chunk 预览
    chunks_preview = [
        {
            "chunk_id": c["chunk_id"],
            "page": c["page"],
            "block_type": c.get("block_type", "page_text"),
            "content": c["content"][:300],
            "content_length": c["content_length"],
        }
        for c in chunks[:30]
    ]

    return {
        "file_name": file_name,
        "doc_id": doc_id,
        "total_pages": total_pages,
        "shown_pages": min(max_pages, len(pages_data)),
        "total_chunks": total_chunks,
        "chunk_types": dict(chunk_types),
        "pages": pages_data,
        "chunks_preview": chunks_preview,
        "config": {
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
            "min_image_width": getattr(settings, "min_image_width", 300),
            "min_image_height": getattr(settings, "min_image_height", 300),
            "header_margin_ratio": getattr(settings, "header_margin_ratio", 0.06),
            "footer_margin_ratio": getattr(settings, "footer_margin_ratio", 0.06),
            "enable_vlm": getattr(settings, "enable_vlm_image_semantics", False),
            "embedding_model": settings.embedding_model_path or settings.embedding_model,
        },
    }
