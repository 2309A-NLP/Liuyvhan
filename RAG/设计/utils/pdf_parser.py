from __future__ import annotations
"""
PDF 解析核心，逐页提取文本，支持 OCR、图片提取、文本清洗
"""
import io    #内存字节流，常配合图片/OCR 使用
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path    # 更方便地处理文件路径
from typing import Any      # 类型注解，表示任意类型

import requests

from config import SETTINGS
from utils.pdf_cleaner import clean_pdf_page_text, discover_repeated_page_artifacts
# clean_pdf_page_text：清理单页 PDF 文本
# discover_repeated_page_artifacts：找重复页眉页脚噪音

"""装图片信息的小容器"""
@dataclass(slots=True)  # 自动帮你生成初始化、打印等样板代码
class PDFImageAsset:
    page_number: int    # 图片来自第几页
    image_index: int    # 这一页里的第几张图
    filename: str       # 图片文件名
    width: int          # 图片宽度
    height: int         # 图片高度

"""它就是一个“存储单页 PDF 解析结果”的对象构造器"""
@dataclass(slots=True)
class PDFPageParseResult:
    page_number: int      # 页码
    text: str             # 清洗后的文本
    raw_text: str         # 原始文本
    used_ocr: bool = False  # 这页是否用了 OCR  你这行里的 = False 是默认值，意思是默认没用 OCR
    image_count: int = 0  # 这页图片数量
    images: list[PDFImageAsset] = field(default_factory=list) # 这页图片信息列表

"""整份 PDF 解析结果”的容器"""
@dataclass(slots=True)
class PDFParseResult:
    pdf_path: str         # PDF 文件路径
    page_count: int       # 总页数
    full_text: str        # 整份 PDF 拼接后的文本
    pages: list[PDFPageParseResult] # 每一页的解析结果列表
    metadata: dict[str, Any] = field(default_factory=dict) # 额外信息，比如是否启用 OCR、解析器名称等

    # 这是把 PDFParseResult 对象转换成字典
    # 作用 - 存成 JSON  打印  写文件
    # 这个方法就是把解析结果整理成可 JSON 化的数据
    def to_dict(self) -> dict[str, Any]:
        return {
            "pdf_path": self.pdf_path,
            "page_count": self.page_count,
            "full_text": self.full_text,
            "pages": [asdict(page) for page in self.pages],
            "metadata": self.metadata,
        }


class MinerUParserBackend:
    # 定义构造函数
    def __init__(
        self,
        *,
        api_url: str,                         # 保存 MinerU 接口地址，并去掉首尾空白和结尾 /
        backend: str = "hybrid-auto-engine",  # 设置解析后端模式
        language: str = "ch",                 # 设置语言
        enable_formula: bool = True,
        enable_table: bool = True,
        image_analysis: bool = True,          # 控制是否识别公式、表格、图片
        timeout: int = 300,                   #
        api_token: str = "",
        start_page_id: int = 0,
        end_page_id: int | None = None,
        logger=None,
    ) -> None:
        # 把这些配置真正初始化到对象里
        self.api_url = api_url.strip().rstrip("/")  # 保存 MinerU 接口地址，并去掉首尾空白和结尾 /
        self.api_token = api_token.strip()
        self.backend = backend
        self.language = language
        self.enable_formula = enable_formula
        self.enable_table = enable_table
        self.image_analysis = image_analysis
        self.timeout = max(1, int(timeout))  # 设置请求超时时间，且最少为 1 秒
        self.start_page_id = max(0, int(start_page_id))
        self.end_page_id = end_page_id if end_page_id is None else max(0, int(end_page_id))
        # 设置只解析哪些页，并把值转成合法整数
        self.logger = logger

    """把 PDF 发给 MinerU 解析，拿回 markdown，再整理成 PDFParseResult"""
    def parse(self, pdf_path: str | Path) -> PDFParseResult:
        # 定义解析入口，输入 PDF 路径，输出整份解析结果对象
        pdf_file = Path(pdf_path).expanduser().resolve() # 把路径转成 Path 对象，展开 ~，并变成绝对路径
        # Path(pdf_path) ---  把传进来的路径字符串，转换成 Path 对象
        # 
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_file}")
        if not self.api_url:
            raise RuntimeError("MINERU_API_URL is empty.")

        markdown_text = self._parse_markdown(pdf_file)
        pages = self._build_pages(markdown_text)
        return PDFParseResult(
            pdf_path=str(pdf_file),
            page_count=len(pages),
            full_text="\n\n".join(f"[Page {page.page_number}]\n{page.text}" for page in pages if page.text.strip()).strip(),
            pages=pages,
            metadata={
                "parser": "mineru",
                "api_url": self.api_url,
                "backend": self.backend,
                "language": self.language,
                "enable_formula": self.enable_formula,
                "enable_table": self.enable_table,
                "image_analysis": self.image_analysis,
            },
        )

    def _parse_markdown(self, pdf_file: Path) -> str:
        if "/api/v4/file-urls/batch" in self.api_url:
            return self._parse_via_official_batch_api(pdf_file)
        if "/agent" in self.api_url or self.api_url.endswith("/agent"):
            return self._parse_via_agent_api(pdf_file)
        return self._parse_via_local_api(pdf_file)

    def _parse_via_official_batch_api(self, pdf_file: Path) -> str:
        if not self.api_token:
            raise RuntimeError("MINERU_API_TOKEN is empty.")

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "enable_formula": self.enable_formula,
            "enable_table": self.enable_table,
            "language": self.language,
            "files": [
                {
                    "name": pdf_file.name,
                    "is_ocr": self.image_analysis,
                    "data_id": f"rag-{int(time.time())}-{pdf_file.stem}",
                }
            ],
        }

        self._log("info", f"MinerU official batch submit: {self.api_url}")
        submit_resp = requests.post(self.api_url, json=payload, headers=headers, timeout=self.timeout)
        submit_resp.raise_for_status()
        submit_data = submit_resp.json()
        batch_id = self._extract_batch_id(submit_data)
        upload_url = self._extract_upload_url(submit_data)

        with pdf_file.open("rb") as fp:
            upload_resp = requests.put(upload_url, data=fp, timeout=self.timeout)
            upload_resp.raise_for_status()

        result_url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
        start = time.time()
        while time.time() - start < self.timeout:
            result_resp = requests.get(result_url, headers=headers, timeout=self.timeout)
            result_resp.raise_for_status()
            result_data = result_resp.json()
            markdown = self._extract_markdown_from_batch_result(result_data)
            if markdown:
                return markdown

            result_text = json.dumps(result_data, ensure_ascii=False)
            if any(flag in result_text.lower() for flag in ("failed", "error", "abort")):
                raise RuntimeError(f"MinerU batch parse failed: {result_text[:500]}")
            time.sleep(3)

        raise TimeoutError(f"MinerU official batch parse timeout after {self.timeout}s for {pdf_file}")

    def _parse_via_agent_api(self, pdf_file: Path) -> str:
        base_url = self.api_url.rstrip("/")
        submit_url = f"{base_url}/parse/file"
        payload: dict[str, Any] = {
            "file_name": pdf_file.name,
            "language": self.language,
            "enable_table": self.enable_table,
            "is_ocr": self.image_analysis,
            "enable_formula": self.enable_formula,
        }
        page_range = self._build_page_range()
        if page_range:
            payload["page_range"] = page_range

        self._log("info", f"MinerU agent submit: {submit_url}")
        response = requests.post(submit_url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if data.get("code") != 0:
            raise RuntimeError(f"MinerU submit failed: {data}")

        task_id = data["data"]["task_id"]
        file_url = data["data"]["file_url"]
        with pdf_file.open("rb") as fp:
            upload = requests.put(file_url, data=fp, timeout=self.timeout)
            upload.raise_for_status()

        result_url = f"{base_url}/parse/{task_id}"
        start = time.time()
        while time.time() - start < self.timeout:
            status = requests.get(result_url, timeout=self.timeout).json()
            state = status.get("data", {}).get("state")
            if state == "done":
                markdown_url = status["data"].get("markdown_url")
                if not markdown_url:
                    raise RuntimeError(f"MinerU result missing markdown_url: {status}")
                md_resp = requests.get(markdown_url, timeout=self.timeout)
                md_resp.raise_for_status()
                return md_resp.text
            if state == "failed":
                raise RuntimeError(f"MinerU parse failed: {status['data'].get('err_msg', 'unknown error')}")
            time.sleep(2)
        raise TimeoutError(f"MinerU parse timeout after {self.timeout}s for {pdf_file}")

    def _parse_via_local_api(self, pdf_file: Path) -> str:
        file_parse_url = f"{self.api_url.rstrip('/')}/file_parse"
        form_data: dict[str, str] = {
            "return_md": "true",
            "response_format_zip": "false",
            "return_original_file": "false",
        }
        self._log("info", f"MinerU local api submit: {file_parse_url}")
        with pdf_file.open("rb") as fp:
            response = requests.post(
                file_parse_url,
                files={"files": (pdf_file.name, fp, "application/pdf")},
                data=form_data,
                timeout=self.timeout,
            )
        response.raise_for_status()
        return self._extract_markdown_payload(response)

    def _extract_markdown_payload(self, response: requests.Response) -> str:
        content_type = response.headers.get("Content-Type", "").lower()
        if "application/json" in content_type:
            data = response.json()
            if isinstance(data, dict):
                for key in ("markdown", "content", "text", "result"):
                    value = data.get(key)
                    if isinstance(value, str) and value.strip():
                        return value
                nested = data.get("data")
                if isinstance(nested, dict):
                    for key in ("markdown", "content", "text", "result"):
                        value = nested.get(key)
                        if isinstance(value, str) and value.strip():
                            return value
                    markdown_url = nested.get("markdown_url")
                    if isinstance(markdown_url, str) and markdown_url:
                        md_resp = requests.get(markdown_url, timeout=self.timeout)
                        md_resp.raise_for_status()
                        return md_resp.text
            raise RuntimeError(f"MinerU response has unexpected json shape: {str(data)[:300]}")

        if response.text.strip():
            return response.text

        raise RuntimeError("MinerU response is empty.")

    @staticmethod
    def _extract_batch_id(data: dict[str, Any]) -> str:
        for key in ("batch_id", "id"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
        nested = data.get("data")
        if isinstance(nested, dict):
            for key in ("batch_id", "id"):
                value = nested.get(key)
                if isinstance(value, str) and value:
                    return value
        raise RuntimeError(f"MinerU batch response missing batch_id: {str(data)[:500]}")

    @staticmethod
    def _extract_upload_url(data: dict[str, Any]) -> str:
        candidates = [data]
        nested = data.get("data")
        if isinstance(nested, dict):
            candidates.append(nested)

        for item in candidates:
            files = item.get("files")
            if isinstance(files, list) and files:
                file_item = files[0]
                if isinstance(file_item, dict):
                    for key in ("upload_url", "presigned_url", "url"):
                        value = file_item.get(key)
                        if isinstance(value, str) and value:
                            return value
            for key in ("upload_url", "presigned_url", "url"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    return value

        raise RuntimeError(f"MinerU batch response missing upload url: {str(data)[:500]}")

    def _extract_markdown_from_batch_result(self, data: dict[str, Any]) -> str:
        markdown_url = self._find_markdown_url(data)
        if markdown_url:
            md_resp = requests.get(markdown_url, timeout=self.timeout)
            md_resp.raise_for_status()
            return md_resp.text

        return self._find_markdown_text(data)

    @staticmethod
    def _find_markdown_url(data: Any) -> str:
        if isinstance(data, dict):
            for key, value in data.items():
                if key in {"full_md_url", "markdown_url", "md_url"} and isinstance(value, str) and value:
                    return value
                found = MinerUParserBackend._find_markdown_url(value)
                if found:
                    return found
        elif isinstance(data, list):
            for item in data:
                found = MinerUParserBackend._find_markdown_url(item)
                if found:
                    return found
        return ""

    @staticmethod
    def _find_markdown_text(data: Any) -> str:
        if isinstance(data, dict):
            for key, value in data.items():
                if key in {"full_md", "markdown", "md_content"} and isinstance(value, str) and value.strip():
                    return value
                found = MinerUParserBackend._find_markdown_text(value)
                if found:
                    return found
        elif isinstance(data, list):
            for item in data:
                found = MinerUParserBackend._find_markdown_text(item)
                if found:
                    return found
        return ""

    def _build_pages(self, markdown_text: str) -> list[PDFPageParseResult]:
        text = (markdown_text or "").strip()
        if not text:
            return []

        parts = self._split_pages(text)
        pages: list[PDFPageParseResult] = []
        for index, part in enumerate(parts, start=1):
            cleaned = part.strip()
            if not cleaned:
                continue
            pages.append(
                PDFPageParseResult(
                    page_number=index,
                    raw_text=cleaned,
                    text=cleaned,
                    used_ocr=False,
                    image_count=0,
                    images=[],
                )
            )
        return pages or [
            PDFPageParseResult(
                page_number=1,
                raw_text=text,
                text=text,
                used_ocr=False,
                image_count=0,
                images=[],
            )
        ]

    @staticmethod
    def _split_pages(text: str) -> list[str]:
        candidates = [
            part.strip()
            for part in re.split(r"\n\s*(?:\f|\[\s*Page\s+\d+\s*\]|Page\s+\d+\s*/\s*\d+)\s*\n", text)
            if part.strip()
        ]
        return candidates if len(candidates) > 1 else [text]

    def _build_page_range(self) -> str | None:
        if self.end_page_id is None or self.end_page_id <= self.start_page_id:
            return None
        return f"{self.start_page_id + 1}-{self.end_page_id}"

    def _log(self, level: str, message: str) -> None:
        if not self.logger:
            return
        log_fn = getattr(self.logger, level, None)
        if callable(log_fn):
            log_fn(message)


class PDFParser:
    def __init__(
        self,
        *,
        ocr_enabled: bool = False,
        ocr_lang: str = "chi_sim+eng",
        tesseract_cmd: str = "",
        extract_images: bool = False,
        image_output_dir: Path | None = None,
        min_text_chars: int = 40,
        logger=None,
    ) -> None:
        self.ocr_enabled = ocr_enabled
        self.ocr_lang = ocr_lang
        self.tesseract_cmd = tesseract_cmd.strip()
        self.extract_images = extract_images
        self.image_output_dir = Path(image_output_dir) if image_output_dir else None
        self.min_text_chars = max(1, min_text_chars)
        self.logger = logger
        self.backend_name = "pymupdf"
        self.mineru_backend: MinerUParserBackend | None = None

    def _init_backend(self) -> None:
        if self.backend_name != "pymupdf" or self.mineru_backend is not None:
            return
        self.backend_name = "pymupdf"

    def parse(self, pdf_path: str | Path) -> PDFParseResult:
        pdf_file = Path(pdf_path).expanduser().resolve()
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_file}")

        if self._should_use_mineru():
            if self.mineru_backend is None:
                self.mineru_backend = MinerUParserBackend(
                    api_url=SETTINGS.mineru_api_url,
                    backend=SETTINGS.mineru_backend,
                    language=SETTINGS.mineru_language,
                    enable_formula=SETTINGS.mineru_formula_enable,
                    enable_table=SETTINGS.mineru_table_enable,
                    image_analysis=SETTINGS.mineru_image_analysis,
                    timeout=SETTINGS.mineru_timeout,
                    api_token=SETTINGS.mineru_api_token,
                    start_page_id=SETTINGS.mineru_start_page_id,
                    end_page_id=SETTINGS.mineru_end_page_id,
                    logger=self.logger,
                )
            return self.mineru_backend.parse(pdf_file)

        fitz = self._import_fitz()
        if self.extract_images and self.image_output_dir:
            self.image_output_dir.mkdir(parents=True, exist_ok=True)

        pages: list[PDFPageParseResult] = []
        with fitz.open(pdf_file) as document:
            for index, page in enumerate(document, start=1):
                raw_text = (page.get_text("text") or "").strip()
                used_ocr = False
                if self.ocr_enabled and len(raw_text) < self.min_text_chars:
                    ocr_text = self._ocr_page(page, fitz)
                    if ocr_text.strip():
                        raw_text = f"{raw_text}\n{ocr_text}".strip() if raw_text else ocr_text.strip()
                        used_ocr = True

                image_assets = self._extract_images(document, page, page_number=index)
                pages.append(
                    PDFPageParseResult(
                        page_number=index,
                        raw_text=raw_text,
                        text=raw_text,
                        used_ocr=used_ocr,
                        image_count=len(image_assets),
                        images=image_assets,
                    )
                )

        repeated_artifacts = discover_repeated_page_artifacts([page.raw_text for page in pages])
        for page in pages:
            page.text = clean_pdf_page_text(page.raw_text, repeated_artifacts)

        full_text = "\n\n".join(
            f"[Page {page.page_number}]\n{page.text}" for page in pages if page.text.strip()
        ).strip()
        return PDFParseResult(
            pdf_path=str(pdf_file),
            page_count=len(pages),
            full_text=full_text,
            pages=pages,
            metadata={
                "parser": "pymupdf",
                "ocr_enabled": self.ocr_enabled,
                "extract_images": self.extract_images,
                "repeated_artifact_count": len(repeated_artifacts),
            },
        )

    def _should_use_mineru(self) -> bool:
        backend = str(getattr(SETTINGS, "pdf_parser_backend", "pymupdf")).strip().lower()
        api_url = str(getattr(SETTINGS, "mineru_api_url", "")).strip()
        return backend == "mineru" and bool(api_url)

    @staticmethod
    def _import_fitz():
        try:
            import fitz  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "PyMuPDF is not installed. Install it first: pip install PyMuPDF"
            ) from exc
        return fitz

    def _ocr_page(self, page, fitz_module) -> str:
        try:
            import pytesseract  # type: ignore
            from PIL import Image
        except ImportError:
            self._log("warning", "OCR skipped because pytesseract is not installed.")
            return ""

        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

        matrix = fitz_module.Matrix(2, 2)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        try:
            return pytesseract.image_to_string(image, lang=self.ocr_lang).strip()
        except Exception as exc:  # noqa: BLE001
            self._log("warning", f"OCR failed on page {page.number + 1}: {exc}")
            return ""

    def _extract_images(self, document, page, *, page_number: int) -> list[PDFImageAsset]:
        if not self.extract_images:
            return []

        assets: list[PDFImageAsset] = []
        for image_index, image_info in enumerate(page.get_images(full=True), start=1):
            xref = image_info[0]
            try:
                extracted = document.extract_image(xref)
            except Exception as exc:  # noqa: BLE001
                self._log("warning", f"Image extraction failed on page {page_number}: {exc}")
                continue

            extension = extracted.get("ext", "png")
            filename = f"page_{page_number:04d}_img_{image_index:02d}.{extension}"
            if self.image_output_dir:
                output_path = self.image_output_dir / filename
                output_path.write_bytes(extracted["image"])

            assets.append(
                PDFImageAsset(
                    page_number=page_number,
                    image_index=image_index,
                    filename=filename,
                    width=int(extracted.get("width", 0) or 0),
                    height=int(extracted.get("height", 0) or 0),
                )
            )
        return assets

    def _log(self, level: str, message: str) -> None:
        if not self.logger:
            return
        log_fn = getattr(self.logger, level, None)
        if callable(log_fn):
            log_fn(message)
