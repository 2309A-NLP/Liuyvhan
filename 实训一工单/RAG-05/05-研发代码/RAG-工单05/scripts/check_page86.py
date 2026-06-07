"""检查第86页 - 540张图片"""
import sys, os
os.chdir(r"C:\Users\刘禹含\Desktop\RAG-工单04")
sys.path.insert(0, os.getcwd())

log_path = r"C:\Users\刘禹含\Desktop\RAG-工单04\page86_check.log"
log = open(log_path, "w", encoding="utf-8")
def pr(msg):
    log.write(msg + "\n")
    log.flush()

from app.core.config import settings
import pdfplumber

file_path = settings.raw_dir / "招股说明书2.pdf"
pdf = pdfplumber.open(file_path)

page = pdf.pages[85]  # 0-indexed
imgs = page.images or []
pr(f"Page86: {len(imgs)} images")

# Show all unique sizes
sizes = {}
for i, img in enumerate(imgs):
    w = int(img.get("width", 0) or 0)
    h = int(img.get("height", 0) or 0)
    key = f"{w}x{h}"
    sizes[key] = sizes.get(key, 0) + 1

pr(f"\nUnique sizes:")
for size, count in sorted(sizes.items()):
    is_large = all(int(x) >= settings.min_image_width for x in size.split('x'))
    pr(f"  {size}: {count} images {'[LARGE]' if is_large else ''}")

large_count = sum(1 for img in imgs if int(img.get("width",0) or 0)>=settings.min_image_width and int(img.get("height",0) or 0)>=settings.min_image_height)
pr(f"\nTotal large images: {large_count}")

pdf.close()
pr("Done")
log.close()
