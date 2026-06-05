# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'C:\Users\刘禹含\Desktop\RAG-工单04')

import pdfplumber
import re
from app.core.config import settings

patterns = settings.watermark_text_patterns
print("配置:", repr(patterns))

# Check PDF2 first (smaller, 350 pages)
pdf_path = r'C:\Users\刘禹含\Desktop\RAG-工单04\data\raw\招股说明书2.pdf'

with pdfplumber.open(pdf_path) as pdf:
    print(f"PDF2 总页数: {len(pdf.pages)}")
    
    for marker in ["招股意向书（申报稿）", "招股说明书（申报稿）"]:
        found_pages = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            if marker in text:
                found_pages.append(i + 1)
        print(f"'{marker}': {len(found_pages)} 页")
        if found_pages:
            print(f"  前10页: {found_pages[:10]}")
    
    # Check what DOES exist in header
    print("\n首行检查（前5页+后5页）:")
    for i in [0,1,2,3,4, 345,346,347,348,349]:
        if i < len(pdf.pages):
            text = pdf.pages[i].extract_text(x_tolerance=2, y_tolerance=2) or ""
            first_line = text.split('\n')[0] if text else "(空)"
            print(f"  第{i+1}页: {first_line[:60]}")
    
    # Check footer (last line)
    print("\n末行检查（前5页+后5页）:")
    for i in [0,1,2,3,4, 345,346,347,348,349]:
        if i < len(pdf.pages):
            text = pdf.pages[i].extract_text(x_tolerance=2, y_tolerance=2) or ""
            lines = [l for l in text.split('\n') if l.strip()]
            last_line = lines[-1] if lines else "(空)"
            print(f"  第{i+1}页: {last_line[:60]}")
