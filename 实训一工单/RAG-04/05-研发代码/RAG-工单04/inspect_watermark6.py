"""Verify that header crop actually removes watermark text, and count real vs watermark images."""
import pdfplumber

path = 'data/raw/招股说明书2.pdf'
with pdfplumber.open(path) as pdf:
    page = pdf.pages[39]  # page 40
    h = float(page.height)
    w = float(page.width)
    
    # Apply the same crop as pdf_service.py
    hm, fm = 0.06, 0.06
    crop_bbox = (0, h * hm, w, h * (1 - fm))
    print(f'Crop bbox: {crop_bbox}')
    print(f'Header zone: 0 to {h*hm:.1f}')
    print(f'Footer zone: {h*(1-fm):.1f} to {h:.1f}')
    
    main_area = page.within_bbox(crop_bbox)
    cropped_text = main_area.extract_text(x_tolerance=2, y_tolerance=2) or ''
    full_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ''
    
    # Check if "招股意向书" appears in cropped vs full text
    for kw in ['招股意向书', '申报稿', '武汉力源']:
        in_full = kw in full_text
        in_cropped = kw in cropped_text
        print(f'  "{kw}": in full={in_full}, in cropped={in_cropped}')
    
    # Now count REAL images vs watermark images on page 310
    print(f'\n=== Page 310 image analysis ===')
    pg310 = pdf.pages[309]
    for i, img in enumerate(pg310.images):
        stream = img.get('stream')
        has_smask = stream and hasattr(stream, 'attrs') and 'SMask' in stream.attrs
        w = img.get('width', 0)
        h2 = img.get('height', 0)
        print(f'  Image {i}: size={w:.0f}x{h2:.0f} pt, has_SMask={has_smask}')
    
    # Count watermark vs real images across all pages
    print(f'\n=== Full document stats ===')
    total_wm = 0
    total_real = 0
    for page in pdf.pages:
        for img in page.images:
            stream = img.get('stream')
            has_smask = stream and hasattr(stream, 'attrs') and 'SMask' in stream.attrs
            if has_smask:
                total_wm += 1
            else:
                total_real += 1
    print(f'  Watermark images (SMask): {total_wm}')
    print(f'  Real content images (no SMask): {total_real}')
    print(f'  Total: {total_wm + total_real}')
