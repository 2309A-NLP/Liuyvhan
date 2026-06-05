import pdfplumber

path = 'data/raw/招股说明书2.pdf'
with pdfplumber.open(path) as pdf:
    for pg in [5, 10, 20, 30, 40, 50, 60, 70, 100, 150, 200, 250, 300, 310]:
        page = pdf.pages[pg-1]
        chars = page.chars
        
        rotated = [c for c in chars if c.get('matrix') and (abs(c['matrix'][1]) > 0.01 or abs(c['matrix'][3]) > 0.01)]
        nonstd = [c for c in chars if c.get('render_mode',0) != 0]
        nonblack = []
        for c in chars:
            nc = c.get('non_stroking_color')
            if nc is not None and str(nc) not in ["(0,)", "(0.0, 0.0, 0.0)"]:
                nonblack.append(c)
        
        print(f'Page {pg}: {len(chars)} chars, rotated={len(rotated)}, nonstd_render={len(nonstd)}, nonblack={len(nonblack)}')
        
        text = page.extract_text(x_tolerance=2, y_tolerance=2) or ''
        for kw in ['招股意向书', '申报稿', '水印', '武汉力源']:
            if kw in text:
                pos = text.find(kw)
                ctx = text[max(0,pos-20):pos+40]
                print(f'  Found "{kw}": ...{repr(ctx)}...')
        
        if rotated:
            for c in rotated[:3]:
                print(f'  Rotated: text="{c["text"]}" matrix={c["matrix"]} size={c["size"]}')
        
        print()

print("\n=== All char keys from page 1 ===")
with pdfplumber.open(path) as pdf:
    page = pdf.pages[0]
    if page.chars:
        print(sorted(page.chars[0].keys()))
