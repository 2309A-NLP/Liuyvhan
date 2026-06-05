import pdfplumber

path = 'data/raw/招股说明书2.pdf'
with pdfplumber.open(path) as pdf:
    page = pdf.pages[0]
    h = float(page.height)
    w = float(page.width)
    print(f'Page 0: {w}x{h}')
    
    # Find "招股意向书" chars
    text = page.extract_text(x_tolerance=2, y_tolerance=2) or ''
    print(f'\nFirst 300 chars of raw text:')
    print(repr(text[:300]))
    
    # Check all chars near the top (potential header)
    top_margin = h * 0.06
    bottom_margin = h * 0.94
    print(f'\nHeader crop zone: 0 to {top_margin:.1f}')
    print(f'Footer crop zone: {bottom_margin:.1f} to {h:.1f}')
    
    top_chars = [c for c in page.chars if c['top'] < top_margin]
    bottom_chars = [c for c in page.chars if c['top'] > bottom_margin]
    middle_chars = [c for c in page.chars if top_margin <= c['top'] <= bottom_margin]
    
    top_text = ''.join(c['text'] for c in sorted(top_chars, key=lambda c: (c['top'], c['x0'])))
    bottom_text = ''.join(c['text'] for c in sorted(bottom_chars, key=lambda c: (c['top'], c['x0'])))
    middle_text = ''.join(c['text'] for c in sorted(middle_chars, key=lambda c: (c['top'], c['x0'])))
    
    print(f'\nTop zone chars ({len(top_chars)}): {repr(top_text[:200])}')
    print(f'\nMiddle zone chars ({len(middle_chars)}): {repr(middle_text[:200])}')
    print(f'\nBottom zone chars ({len(bottom_chars)}): {repr(bottom_text[:200])}')

    # Check page 40 for watermark-like chars (large, special tags)
    print('\n\n=== Page 40 deep dive ===')
    page = pdf.pages[39]
    h = float(page.height)
    
    # Check for any chars with special tags 
    tags = {}
    for c in page.chars:
        tag = c.get('tag', 'none')
        tags[tag] = tags.get(tag, 0) + 1
    print(f'Char tags: {tags}')
    
    # Check ncs (non-stroking color space)
    ncss = {}
    for c in page.chars:
        ncs = c.get('ncs', 'none')
        ncss[str(ncs)] = ncss.get(str(ncs), 0) + 1
    print(f'Color spaces: {ncss}')
    
    # Check for any MCID or struct parent
    has_mcid = any(c.get('mcid') is not None for c in page.chars)
    print(f'Has MCID: {has_mcid}')
    
    # Check for any "watermark" object types
    otypes = {}
    for obj in page.objects:
        ot = obj.get('object_type', '?')
        otypes[ot] = otypes.get(ot, 0) + 1
    print(f'\nObject types on page 40:')
    for ot, cnt in sorted(otypes.items(), key=lambda x: -x[1]):
        print(f'  {ot}: {cnt}')
    
    # List all non-char objects (shapes, lines, images)
    print(f'\nNon-char objects on page 40:')
    for obj in page.objects:
        if obj.get('object_type') != 'char' and obj.get('object_type') != 'text':
            ot = obj.get('object_type', '?')
            print(f'  type={ot}', end='')
            if 'x0' in obj:
                print(f' bbox=({obj.get("x0",0):.0f},{obj.get("top",0):.0f},{obj.get("x1",0):.0f},{obj.get("bottom",0):.0f})', end='')
            if 'width' in obj:
                print(f' size={obj.get("width",0):.0f}x{obj.get("height",0):.0f}', end='')
            print()
