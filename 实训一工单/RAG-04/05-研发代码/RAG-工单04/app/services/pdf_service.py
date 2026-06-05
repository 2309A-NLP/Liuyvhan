import hashlib
import re
from pathlib import Path

import pdfplumber
from PIL import Image

from app.core.config import settings


class PDFService:
    def __init__(self, image_semantic_service=None) -> None:
        self.image_semantic_service = image_semantic_service

    def save_upload(self, file_bytes: bytes, file_name: str, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / file_name
        file_path.write_bytes(file_bytes)
        return file_path

    def parse_pdf(self, file_path: Path) -> dict:
        pages: list[dict] = []
        with pdfplumber.open(file_path) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                # 工单编号：人工智能 NLP-RAG-页眉页脚水印过滤
                # 截取正文区域（跳过页眉/页脚/水印等重复内容）
                h = float(page.height)
                w = float(page.width)
                hm = settings.header_margin_ratio
                fm = settings.footer_margin_ratio
                if hm > 0 or fm > 0:
                    crop_bbox = (0, h * hm, w, h * (1 - fm))
                    try:
                        main_area = page.within_bbox(crop_bbox)
                        page_text = main_area.extract_text(x_tolerance=2, y_tolerance=2) or ""
                    except Exception:
                        page_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                else:
                    page_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                # 工单编号：人工智能 NLP-RAG-文字水印过滤
                # 移除提取文本中已知的水印关键词（如"招股意向书（申报稿）"等）
                page_text = self._filter_watermark_text(page_text)
                # 工单编号：人工智能 NLP-RAG-图像内容解析及检索优化
                tables = page.extract_tables() or []
                table_blocks = [
                    self._build_table_block(table=table, table_index=table_index)
                    for table_index, table in enumerate(tables, start=1)
                    if table
                ]
                image_blocks = self._extract_image_blocks(
                    file_path=file_path,
                    page=page,
                    page_index=page_index,
                    page_text=page_text,
                )
                blocks = self._build_page_blocks(
                    page_text=page_text,
                    table_blocks=table_blocks,
                    image_blocks=image_blocks,
                )
                table_texts = [block["content"] for block in table_blocks if block["content"].strip()]
                image_texts = [block["content"] for block in image_blocks if block["content"].strip()]
                merged_text = "\n\n".join(block["content"] for block in blocks if block["content"].strip())
                pages.append(
                    {
                        "page": page_index,
                        "text": merged_text.strip(),
                        "raw_text": page_text.strip(),
                        "tables": table_texts,
                        "images": image_texts,
                        "blocks": blocks,
                    }
                )

        return {
            "doc_id": self.build_doc_id(file_path),
            "file_name": file_path.name,
            "pages": pages,
            "page_count": len(pages),
        }

    def build_doc_id(self, file_path: Path) -> str:
        digest = hashlib.sha1(f"{file_path.name}:{file_path.stat().st_size}".encode("utf-8")).hexdigest()
        return digest[:16]

    def extract_first_page_text(self, file_path: Path) -> str:
        with pdfplumber.open(file_path) as pdf:
            if not pdf.pages:
                return ""
            return (pdf.pages[0].extract_text(x_tolerance=2, y_tolerance=2) or "").strip()

    def _build_page_blocks(self, page_text: str, table_blocks: list[dict], image_blocks: list[dict]) -> list[dict]:
        blocks: list[dict] = []
        cleaned_page_text = page_text.strip()
        if cleaned_page_text:
            blocks.append(
                {
                    "block_type": "page_text",
                    "block_index": 0,
                    "content": cleaned_page_text,
                }
            )

        blocks.extend(table_blocks)
        blocks.extend(image_blocks)
        return blocks

    def _extract_image_blocks(
        self,
        file_path: Path,
        page,
        page_index: int,
        page_text: str,
    ) -> list[dict]:
        if not settings.enable_multimodal_image_parsing or self.image_semantic_service is None:
            return []

        image_dir = settings.image_dir / self.build_doc_id(file_path)
        image_dir.mkdir(parents=True, exist_ok=True)
        image_blocks: list[dict] = []
        page_images = page.images or []
        print(f"  [PDF] 第{page_index}页, 发现{len(page_images)}张图片", flush=True)

        real_index = 0  # independent counter for real images (excluding watermark)
        for image_index, image_info in enumerate(page_images[: settings.max_images_per_page], start=1):
            # 水印过滤：跳过 SMask（软遮罩）图片——这类图片通常是重复的水印背景图案
            if self._is_watermark_image(image_info):
                print(f"  [WATERMARK] 第{page_index}页第{image_index}张图片(跳过,SMask软遮罩水印)", flush=True)
                continue

            width = int(image_info.get("width", 0) or 0)
            height = int(image_info.get("height", 0) or 0)
            if width < settings.min_image_width or height < settings.min_image_height:
                continue

            image = self._crop_page_image(page=page, image_info=image_info)
            if image is None:
                continue

            real_index += 1
            image_path = image_dir / f"page_{page_index:04d}_image_{real_index:02d}.png"
            image.save(image_path)
            print(f"  [IMG] 开始处理第{page_index}页第{real_index}张图片 ({width}x{height})...", flush=True)
            image_block = self.image_semantic_service.describe_image(
                image=image,
                image_path=image_path,
                page_number=page_index,
                image_index=real_index,
                page_text=page_text,
            )
            print(f"  [IMG] 第{page_index}页第{real_index}张图片处理完成", flush=True)
            image_blocks.append(image_block)

        return image_blocks

    def _crop_page_image(self, page, image_info: dict) -> Image.Image | None:
        x0 = float(image_info.get("x0", 0) or 0)
        top = float(image_info.get("top", 0) or 0)
        x1 = float(image_info.get("x1", 0) or 0)
        bottom = float(image_info.get("bottom", 0) or 0)
        if x1 <= x0 or bottom <= top:
            return None

        try:
            cropped_page = page.crop((x0, top, x1, bottom))
            page_image = cropped_page.to_image(resolution=144)
            return page_image.original.convert("RGB")
        except Exception:
            return None

    def _is_watermark_image(self, image_info: dict) -> bool:
        """检测是否为 SMask 水印图片（带软遮罩的重复背景图案）。

        招股说明书 PDF 中常见：每页 15 张 143x127pt 的图片排列成 3×5 网格，
        这些图片的 RGB 内容全黑，但通过 SMask（软遮罩）控制透明度。
        """
        if not settings.enable_watermark_filter:
            return False

        stream = image_info.get("stream")
        if stream is None:
            return False

        # SMask（软遮罩/Soft Mask）= PDF 透明度遮罩，水印图片的典型特征
        attrs = getattr(stream, "attrs", None) or {}
        if "SMask" in attrs:
            return True

        return False

    def _filter_watermark_text(self, text: str) -> str:
        """移除提取文本中已知的水印关键词。

        通过配置文件 WATERMARK_TEXT_PATTERNS 提供模式列表，
        支持正则表达式，用逗号分隔。
        """
        if not text or not settings.enable_watermark_filter:
            return text

        patterns = settings.watermark_text_patterns
        if not patterns:
            return text

        for pattern in patterns.split(","):
            pattern = pattern.strip()
            if not pattern:
                continue
            try:
                text = re.sub(pattern, "", text)
            except re.error:
                # 忽略无效正则，用纯文本替换
                text = text.replace(pattern, "")

        return text.strip()

    def _build_table_block(self, table: list[list[str | None]], table_index: int) -> dict:
        markdown = self._table_to_markdown(table)
        row_text = self._table_to_row_text(table)
        content_parts = [f"【表格{table_index}】"]
        if markdown:
            content_parts.append(markdown)
        if row_text:
            content_parts.append("【表格行文本】\n" + row_text)
        return {
            "block_type": "table",
            "block_index": table_index,
            "content": "\n".join(part for part in content_parts if part.strip()).strip(),
        }

    def _table_to_markdown(self, table: list[list[str | None]]) -> str:
        normalized_rows = [self._normalize_row(row) for row in table]
        normalized_rows = [row for row in normalized_rows if row]

        if not normalized_rows:
            return ""

        header = normalized_rows[0]
        separator = ["---" for _ in header]
        body = normalized_rows[1:] if len(normalized_rows) > 1 else []

        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        for row in body:
            padded_row = row + [""] * max(0, len(header) - len(row))
            lines.append("| " + " | ".join(padded_row[: len(header)]) + " |")
        return "\n".join(lines)

    def _table_to_row_text(self, table: list[list[str | None]]) -> str:
        normalized_rows = [self._normalize_row(row) for row in table]
        normalized_rows = [row for row in normalized_rows if row]
        if not normalized_rows:
            return ""

        if len(normalized_rows) == 1:
            return " | ".join(normalized_rows[0])

        header = normalized_rows[0]
        body = normalized_rows[1:]
        lines: list[str] = []

        if self._looks_like_header(header=header, body=body):
            for row in body:
                cells: list[str] = []
                for index, value in enumerate(row):
                    column_name = header[index] if index < len(header) else f"列{index + 1}"
                    cells.append(f"{column_name}: {value}")
                if cells:
                    lines.append("；".join(cells))
            return "\n".join(lines)

        for row in normalized_rows:
            lines.append(" | ".join(row))
        return "\n".join(lines)

    def _normalize_row(self, row: list[str | None]) -> list[str]:
        cleaned = [self._clean_cell(cell) for cell in row]
        return [cell for cell in cleaned if cell]

    def _looks_like_header(self, header: list[str], body: list[list[str]]) -> bool:
        if not header or not body:
            return False

        header_text = "".join(header)
        if any(token in header_text for token in ["序号", "名称", "项目", "金额", "比例", "关系", "股东", "年份", "收入"]):
            return True

        return all(len(row) <= len(header) for row in body[:5])

    def _clean_cell(self, value: str | None) -> str:
        return re.sub(r"\s+", " ", (value or "").replace("\n", " ")).strip()
