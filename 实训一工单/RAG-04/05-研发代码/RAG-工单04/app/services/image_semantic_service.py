import base64
import io
import threading
from pathlib import Path

from openai import OpenAI

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

try:
    from transformers import CLIPModel, CLIPProcessor
except Exception:  # pragma: no cover
    CLIPModel = None
    CLIPProcessor = None

from app.core.config import settings


class ImageSemanticService:
    # 工单编号：人工智能 NLP-RAG-图像内容解析及检索优化
    CLIP_LABEL_CANDIDATES = [
        "组织结构图",
        "架构图",
        "流程图",
        "柱状图",
        "折线图",
        "饼图",
        "趋势图",
        "市场应用结构图",
        "股权结构图",
        "业务流程图",
        "产品示意图",
        "表格截图",
        "带文字的统计图",
        "带文字的说明图片",
        "公司部门结构图",
        "销售组织结构图",
    ]

    def __init__(self) -> None:
        self.clip_processor = None
        self.clip_model = None
        self.vlm_client = None
        self._clip_initialized = False
        self._vlm_initialized = False
        self._clip_lock = threading.Lock()

    def describe_image(
        self,
        image: Image.Image,
        image_path: Path,
        page_number: int,
        image_index: int,
        page_text: str,
    ) -> dict:
        semantic_parts: list[str] = []
        self._ensure_clip_initialized()
        self._ensure_vlm_initialized()
        clip_result = self._classify_with_clip(image)
        if clip_result:
            semantic_parts.append(
                "CLIP语义标签: " + "，".join(
                    f"{item['label']}({item['score']:.3f})" for item in clip_result
                )
            )

        neighbor_text = self._extract_neighbor_text(page_text)
        if neighbor_text:
            semantic_parts.append(f"页面邻近文本: {neighbor_text}")

        vlm_description = self._describe_with_vlm(image)
        if vlm_description:
            semantic_parts.append(f"多模态描述: {vlm_description}")

        content = (
            f"【图片{image_index}】第{page_number}页图片语义解析。\n"
            f"图片文件: {image_path.name}\n"
            + "\n".join(semantic_parts)
        ).strip()

        return {
            "block_type": "image",
            "block_index": image_index,
            "image_path": str(image_path),
            "clip_labels": clip_result,
            "vlm_description": vlm_description,
            "content": content,
        }

    def _init_clip(self) -> None:
        if not settings.enable_multimodal_image_parsing or not settings.enable_clip_image_semantics:
            return
        if CLIPModel is None or CLIPProcessor is None:
            return

        model_source = settings.clip_model_path.strip() or settings.clip_model_name
        try:
            self.clip_processor = CLIPProcessor.from_pretrained(model_source, local_files_only=bool(settings.clip_model_path.strip()))
            self.clip_model = CLIPModel.from_pretrained(model_source, local_files_only=bool(settings.clip_model_path.strip()))
        except Exception:
            self.clip_processor = None
            self.clip_model = None
        finally:
            self._clip_initialized = True

    def _init_vlm(self) -> None:
        if not settings.enable_multimodal_image_parsing or not settings.enable_vlm_image_semantics:
            return
        if not settings.llm_api_key:
            self._vlm_initialized = True
            return
        self.vlm_client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=120,
        )
        self._vlm_initialized = True

    def _ensure_clip_initialized(self) -> None:
        if not self._clip_initialized:
            self._init_clip()

    def _ensure_vlm_initialized(self) -> None:
        if not self._vlm_initialized:
            self._init_vlm()

    def _classify_with_clip(self, image: Image.Image) -> list[dict]:
        print(f"    [CLIP] 开始分类...", flush=True)
        with self._clip_lock:
            print(f"    [CLIP] 获得锁，开始推理...", flush=True)
            if self.clip_processor is None or self.clip_model is None:
                return []

            try:
                inputs = self.clip_processor(
                    text=self.CLIP_LABEL_CANDIDATES,
                    images=image,
                    return_tensors="pt",
                    padding=True,
                )
                outputs = self.clip_model(**inputs)
                logits_per_image = outputs.logits_per_image[0]
                probs = logits_per_image.softmax(dim=0).tolist()
                ranked = sorted(
                    [
                        {"label": label, "score": float(score)}
                        for label, score in zip(self.CLIP_LABEL_CANDIDATES, probs)
                    ],
                    key=lambda item: item["score"],
                    reverse=True,
                )
                return ranked[:3]
            except Exception:
                return []

    def _describe_with_vlm(self, image: Image.Image) -> str:
        print(f"    [VLM] 开始调用API...", flush=True)
        if self.vlm_client is None:
            return ""

        model_name = settings.multimodal_model.strip() or settings.llm_model
        try:
            buffer = io.BytesIO()
            rgb_image = image.convert("RGB")
            rgb_image.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            response = self.vlm_client.chat.completions.create(
                model=model_name,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": "你负责提取PDF图像的语义信息。请优先识别图表标题、结构层级、关键类别、趋势、增减关系和图片中的中文关键信息，输出一段简洁中文描述。",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "请解析这张PDF图片的语义内容，适合后续RAG检索。"},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                            },
                        ],
                    },
                ],
                timeout=60,
            )
            result = (response.choices[0].message.content or "").strip()
            print(f"    [VLM] API返回成功 ({len(result)}字符)", flush=True)
            return result
        except Exception as e:
            print(f"    [VLM] API调用失败: {type(e).__name__}: {e}", flush=True)
            return ""

    def _extract_neighbor_text(self, page_text: str) -> str:
        text = " ".join((page_text or "").split())
        if not text:
            return ""
        return text[:240]
