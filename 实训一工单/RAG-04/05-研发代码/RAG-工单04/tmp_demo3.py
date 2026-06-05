# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'C:\Users\刘禹含\Desktop\RAG-工单04')

import pdfplumber
import re
from app.core.config import settings

# 检查两个 PDF 的水印文字模式
pdfs = [
    (r'C:\Users\刘禹含\Desktop\RAG-工单04\data\raw\招股说明书1.pdf', "PDF1 兴图新科"),
    (r'C:\Users\刘禹含\Desktop\RAG-工单04\data\raw\招股说明书2.pdf', "PDF2 力源信息"),
]

patterns = settings.watermark_text_patterns
print("配置:", repr(patterns))

for pdf_path, label in pdfs:
    print(f"\n===== {label} =====")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"总页数: {len(pdf.pages)}")
            
            for marker in ["招股意向书（申报稿）", "招股说明书（申报稿）", "招股意向书", "（申报稿）"]:
                found_pages = []
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                    if marker in text:
                        found_pages.append(i + 1)
                print(f"  '{marker}': 出现在 {len(found_pages)} 页")
                if found_pages and len(found_pages) <= 3:
                    print(f"    页码: {found_pages}")
            
            # 检查首行
            print(f"\n  第1页首行: {repr(pdf.pages[0].extract_text(x_tolerance=2, y_tolerance=2)[:80])}")
            print(f"  第100页首行: {repr(pdf.pages[99].extract_text(x_tolerance=2, y_tolerance=2)[:80])}")
    except Exception as e:
        print(f"  错误: {e}")
