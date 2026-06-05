# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'C:\Users\刘禹含\Desktop\RAG-工单04')

import pdfplumber
import re
from app.core.config import settings

pdf_path = r'C:\Users\刘禹含\Desktop\RAG-工单04\data\raw\招股说明书2.pdf'

patterns = settings.watermark_text_patterns
print("=== 配置中的水印文字模式 ===")
print(repr(patterns))

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[1]
    h = float(page.height)
    w = float(page.width)
    hm = settings.header_margin_ratio
    fm = settings.footer_margin_ratio
    
    raw_full_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
    
    crop_bbox = (0, h * hm, w, h * (1 - fm))
    try:
        main_area = page.within_bbox(crop_bbox)
        cropped_text = main_area.extract_text(x_tolerance=2, y_tolerance=2) or ""
    except:
        cropped_text = raw_full_text
    
    text_after_filter = cropped_text
    for p in patterns.split(","):
        p = p.strip()
        if not p:
            continue
        try:
            text_after_filter = re.sub(p, "", text_after_filter)
        except re.error:
            text_after_filter = text_after_filter.replace(p, "")
    text_after_filter = text_after_filter.strip()

    print("\n=== 原始全文（前 800 字符）===")
    print(repr(raw_full_text[:800]))
    
    print("\n=== 物理裁剪后（前 800 字符）===")
    print(repr(cropped_text[:800]))
    
    print("\n=== 文字水印过滤后（前 800 字符）===")
    print(repr(text_after_filter[:800]))
    
    for marker in ["招股意向书（申报稿）", "招股说明书（申报稿）"]:
        print(f"\n--- 检查 '{marker}' ---")
        print(f"  原始全文: {'存在' if marker in raw_full_text else '不存在'}")
        print(f"  裁剪后:   {'存在' if marker in cropped_text else '不存在'}")
        print(f"  过滤后:   {'存在' if marker in text_after_filter else '不存在'}")

    print("\n=== 水印文字在原始文本中的上下文 ===")
    for marker in ["招股意向书（申报稿）", "招股说明书（申报稿）"]:
        idx = raw_full_text.find(marker)
        if idx >= 0:
            start = max(0, idx - 60)
            end = min(len(raw_full_text), idx + len(marker) + 60)
            snippet = raw_full_text[start:end]
            print(f"\n[{marker}]")
            print(f"  ...{repr(snippet)}...")
