from pathlib import Path

import pdfplumber


RAW_DIR = Path("data/raw")


PDF_LABELS = {
    "招股说明书1.pdf": "兴图新科",
    "招股说明书2.pdf": "力源信息",
}


QUERIES = {
    "兴图新科": [
        "武汉兴图新科电子股份有限公司",
        "军用领域",
        "技术标准",
        "国家科技进步一等奖",
        "注册资本",
        "法定代表人",
        "补充流动资金",
        "上游",
        "下游",
        "重要供应商",
    ],
    "力源信息": [
        "武汉力源信息技术股份有限公司",
        "发行股数",
        "募集资金",
        "控制关系",
        "不存在控制关系",
        "关联方",
        "持股比例",
        "本公司关系",
    ],
}


def main() -> None:
    for path in sorted(RAW_DIR.glob("*.pdf")):
        label = PDF_LABELS.get(path.name, path.name)
        print(f"=== {label}: {path.name} ===")
        with pdfplumber.open(path) as pdf:
            for query in QUERIES.get(label, []):
                pages: list[int] = []
                for page_no, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    if query in text:
                        pages.append(page_no)
                print(query, pages[:20])
        print()


if __name__ == "__main__":
    main()
