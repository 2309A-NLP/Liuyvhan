# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'C:\Users\刘禹含\Desktop\RAG-工单04')

import pdfplumber
import re
from app.core.config import settings

pdf_path = r'C:\Users\刘禹含\Desktop\RAG-工单04\data\raw\招股说明书2.pdf'

patterns = settings.watermark_text_patterns
print("配置中的水印文字模式:", repr(patterns))

with pdfplumber.open(pdf_path) as pdf:
    total_pages = len(pdf.pages)
    print(f"总页数: {total_pages}")
    
    for marker in ["招股意向书（申报稿）", "招股说明书（申报稿）"]:
        found_pages = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            if marker in text:
                found_pages.append(i + 1)
                # Show context for first few occurrences
                if len(found_pages) <= 3:
                    idx = text.find(marker)
                    start = max(0, idx - 40)
                    end = min(len(text), idx + len(marker) + 40)
                    print(f"\n{marker} 在第 {i+1} 页:")
                    print(f"  上下文: ...{repr(text[start:end])}...")
        
        print(f"\n{marker}: 出现在 {len(found_pages)} 页中")
        if found_pages:
            print(f"  页码: {found_pages[:20]}{'...' if len(found_pages) > 20 else ''}")
    
    # Also check what the header text actually looks like across pages
    print("\n\n=== 检查各页顶部文本特征（前 200 字符）===")
    for page_num in [0, 1, 2, 3, 4, 50, 100, 200, 300, 349]:
        if page_num < total_pages:
            text = pdf.pages[page_num].extract_text(x_tolerance=2, y_tolerance=2) or ""
            # Get the first line (header)
            first_line = text.split('\n')[0] if text else "(空)"
            print(f"第 {page_num+1} 页首行: {repr(first_line)}")
