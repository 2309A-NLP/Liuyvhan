"""检查招股说明书2.pdf 第249页 - 输出到文件"""
import sys, os
os.chdir(r"C:\Users\刘禹含\Desktop\RAG-工单04")
sys.path.insert(0, os.getcwd())

log_path = r"C:\Users\刘禹含\Desktop\RAG-工单04\page249_check.log"
log = open(log_path, "w", encoding="utf-8")

def pr(msg):
    log.write(msg + "\n")
    log.flush()

from app.core.config import settings
import pdfplumber

file_path = settings.raw_dir / "招股说明书2.pdf"
pr(f"File: {file_path.resolve()}")
pr(f"Exists: {file_path.exists()}")

pdf = pdfplumber.open(file_path)
pr(f"Pages: {len(pdf.pages)}")

# Page 249 (0-indexed = 248)
page = pdf.pages[248]
text = page.extract_text() or ""
pr(f"Page249 text len: {len(text)}")

pr(f"\n--- Page 249 images ---")
imgs = page.images or []
pr(f"Total: {len(imgs)}")

count_large = 0
for i, img in enumerate(imgs):
    w = int(img.get("width", 0) or 0)
    h = int(img.get("height", 0) or 0)
    x0 = img.get("x0", 0)
    top = img.get("top", 0)
    pr(f"  img{i+1}: {w}x{h} @({x0:.0f},{top:.0f})")
    if w >= settings.min_image_width and h >= settings.min_image_height:
        count_large += 1
        pr(f"    -> LARGE (>{settings.min_image_width}x{settings.min_image_height})")
pr(f"Large images on page 249: {count_large}/{len(imgs)}")

# Check pages 245-252
pr(f"\n--- Nearby pages ---")
for pg in range(245, 253):
    if pg >= len(pdf.pages):
        break
    p = pdf.pages[pg]
    n_imgs = len(p.images or [])
    txt = (p.extract_text() or "")[:100]
    large = sum(1 for img in (p.images or []) if int(img.get("width",0) or 0)>=settings.min_image_width and int(img.get("height",0) or 0)>=settings.min_image_height)
    pr(f"Page{pg+1}: {n_imgs}imgs, {large}large, text: {txt}")
    shown = 0
    for img in (p.images or []):
        if shown >= 5: break
        w = int(img.get("width",0) or 0)
        h = int(img.get("height",0) or 0)
        if w>=settings.min_image_width and h>=settings.min_image_height:
            pr(f"   large img: {w}x{h}")
            shown += 1

# Also check pages that had VLM in previous run: 108, 110, 115, 117
pr(f"\n--- Pages with VLM (108,110,115,117) ---")
for pg_num in [108, 110, 115, 117]:
    p = pdf.pages[pg_num - 1]
    n_imgs = len(p.images or [])
    large = sum(1 for img in (p.images or []) if int(img.get("width",0) or 0)>=settings.min_image_width and int(img.get("height",0) or 0)>=settings.min_image_height)
    pr(f"Page{pg_num}: {n_imgs}imgs, {large}large")
    for img in (p.images or []):
        w = int(img.get("width",0) or 0)
        h = int(img.get("height",0) or 0)
        if w>=settings.min_image_width and h>=settings.min_image_height:
            pr(f"   img: {w}x{h}")

pdf.close()
pr("Done")
log.close()
