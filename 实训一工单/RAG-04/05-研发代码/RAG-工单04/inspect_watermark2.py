import pdfplumber

path = 'data/raw/招股说明书2.pdf'
with pdfplumber.open(path) as pdf:
    page = pdf.pages[39]  # page 40
    h = float(page.height)
    
    # Check rects/curves (vector shapes, might be watermark borders)
    print(f'=== Rects on page 40 ===')
    for rect in page.rects:
        print(f'  bbox=({rect["x0"]:.0f},{rect["top"]:.0f},{rect["x1"]:.0f},{rect["bottom"]:.0f}) '
              f'fill={rect.get("non_stroking_color")} stroke={rect.get("stroking_color")} '
              f'fill_opacity={rect.get("fill_opacity")} stroke_opacity={rect.get("stroke_opacity")}')
    
    print(f'\n=== Lines/Curves on page 40 ===')
    for line in getattr(page, 'lines', [])[:5]:
        print(f'  ({line["x0"]:.0f},{line["top"]:.0f})->({line["x1"]:.0f},{line["bottom"]:.0f})')
    
    print(f'\n=== Images on page 40 ===')
    for img in page.images:
        print(f'  bbox=({img["x0"]:.0f},{img["top"]:.0f},{img["x1"]:.0f},{img["bottom"]:.0f}) '
              f'size={img.get("width",0):.0f}x{img.get("height",0):.0f} '
              f'stream={img.get("stream")}')
    
    # Now, ALSO check if the watermark is actually embedded in the images
    # (common in Chinese PDFs - watermark is part of the rendered page background)
    
    # Let's check page 30 (known to have "招股意向书（申报稿）" text)
    print(f'\n\n=== Page 30 detailed text positions ===')
    page30 = pdf.pages[29]
    
    # Get all text positioned in the page center (where watermarks typically are)
    center_texts = []
    for c in page30.chars:
        x0 = c['x0']
        is_center = 100 < x0 < 495  # middle of 595pt page
        if is_center:
            center_texts.append(c)
    
    # Group by approximate y position
    y_groups = {}
    for c in center_texts:
        y_key = round(c['top'], 0)
        if y_key not in y_groups:
            y_groups[y_key] = []
        y_groups[y_key].append(c)
    
    print(f'Center zone chars grouped by y-position:')
    for y in sorted(y_groups.keys(), reverse=False)[:20]:
        chars_at_y = y_groups[y]
        text = ''.join(c['text'] for c in sorted(chars_at_y, key=lambda c: c['x0']))
        sizes = set(f'{c["size"]:.0f}' for c in chars_at_y)
        print(f'  y={y:.0f} font_sizes={",".join(sorted(sizes))}: {repr(text[:80])}')

# NEW: Render page 40 to image and save to check visually
print(f'\n\n=== Rendering page 40 to check for watermark ===')
with pdfplumber.open(path) as pdf:
    page = pdf.pages[39]
    img = page.to_image(resolution=200)
    img.save('data/processed/images/page_40_check.png')
    print('Saved page 40 render to data/processed/images/page_40_check.png')
