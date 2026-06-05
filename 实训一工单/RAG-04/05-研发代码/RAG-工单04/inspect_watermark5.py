"""Analyze watermark patterns across multiple pages."""
import pdfplumber

path = 'data/raw/招股说明书2.pdf'
with pdfplumber.open(path) as pdf:
    print(f'Total pages: {len(pdf.pages)}')
    
    # Count watermark-like images (SMask, repeated pattern) across pages
    print('\n=== Watermark image patterns across pages ===')
    for pg in [0, 5, 10, 20, 30, 40, 50, 60, 70, 100, 150, 200, 250, 300, 310]:
        page = pdf.pages[pg-1] if pg <= len(pdf.pages) else pdf.pages[-1]
        images = page.images
        
        # Count SMask images (watermark candidates)
        watermark_imgs = []
        for img in images:
            stream = img.get('stream')
            if stream and hasattr(stream, 'attrs') and 'SMask' in stream.attrs:
                watermark_imgs.append(img)
        
        print(f'  Page {pg}: {len(images)} images total, {len(watermark_imgs)} with SMask')
        
        # Also check for "招股意向书（申报稿）" text pattern
        # This commonly appears as watermark in Chinese prospectuses
        all_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ''
        
        # Check for suspicious watermarks - text appearing at unusual positions
        chars = page.chars
        # Find chars with unusual sizes (watermarks are often larger)
        large_chars = [c for c in chars if c.get('size', 0) >= 20]
        
        # Look for the watermark text "申报稿" or similar
        has_shenbaogao = '申报稿' in all_text and '招股意向书' in all_text
        
        # Also check the raw unextracted text for patterns
        if has_shenbaogao:
            # Find position of "申报稿"
            pos = all_text.find('申报稿')
            ctx = all_text[max(0,pos-30):pos+30]
            print(f'    Found "申报稿" text near: ...{repr(ctx)}...')
        
        if large_chars:
            # Get unique large texts
            large_text = ''.join(set(c['text'] for c in large_chars))
            print(f'    Large chars (size>=20): {repr(large_text[:80])}')
    
    # Now check PDF1 for comparison
    print('\n\n=== PDF 1 (兴图新科) check ===')
    path1 = 'data/raw/招股说明书1.pdf'
    import os
    if os.path.exists(path1):
        with pdfplumber.open(path1) as pdf1:
            for pg in [0, 10, 20, 30, 40, 50]:
                page = pdf1.pages[pg-1] if pg <= len(pdf1.pages) else pdf1.pages[-1]
                images = page.images
                watermark_imgs = []
                for img in images:
                    stream = img.get('stream')
                    if stream and hasattr(stream, 'attrs') and 'SMask' in stream.attrs:
                        watermark_imgs.append(img)
                
                chars = page.chars
                large_chars = [c for c in chars if c.get('size', 0) >= 20]
                
                text = page.extract_text(x_tolerance=2, y_tolerance=2) or ''
                has_wm = '申报稿' in text or '招股意向书' in text or '招股说明书' in text
                
                print(f'  Page {pg}: {len(images)} images, {len(watermark_imgs)} SMask, {len(large_chars)} large chars, has_wm_text={has_wm}')
                if large_chars:
                    large_text = ''.join(set(c['text'] for c in large_chars))
                    if any(kw in large_text for kw in ['招', '股', '说', '明', '书', '申', '报', '稿']):
                        print(f'    Large chars: {repr(large_text[:100])}')
    else:
        print('  PDF 1 not found at data/raw/招股说明书1.pdf')
