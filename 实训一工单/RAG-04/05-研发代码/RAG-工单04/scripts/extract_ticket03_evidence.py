from pathlib import Path

import pdfplumber


RAW_DIR = Path("data/raw")


TARGET_PAGES = {
    "招股说明书1.pdf": [22, 23, 26, 27, 30, 95, 129, 151, 152, 153, 154, 155],
    "招股说明书2.pdf": [2, 22, 24, 157, 158, 159, 160, 161],
}


def print_page_details(path: Path, page_no: int) -> None:
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[page_no - 1]
        text = page.extract_text() or ""
        print(f"--- PAGE {page_no} TEXT ---")
        print(text[:5000])

        tables = page.extract_tables() or []
        for index, table in enumerate(tables, start=1):
            print(f"--- PAGE {page_no} TABLE {index} ---")
            for row in table[:30]:
                print(row)
        print()


def main() -> None:
    for path in sorted(RAW_DIR.glob("*.pdf")):
        if path.name not in TARGET_PAGES:
            continue
        print(f"===== {path.name} =====")
        for page_no in TARGET_PAGES[path.name]:
            print_page_details(path, page_no)


if __name__ == "__main__":
    main()
