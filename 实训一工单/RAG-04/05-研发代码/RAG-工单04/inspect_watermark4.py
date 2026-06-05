"""Dump the actual image bytes of the repeated watermark-like images."""
import pdfplumber
from PIL import Image
import io

path = 'data/raw/招股说明书2.pdf'
with pdfplumber.open(path) as pdf:
    page = pdf.pages[39]  # page 40
    
    # Try to extract the image stream directly
    for i, img_info in enumerate(page.images[:3]):
        stream_obj = img_info.get('stream')
        print(f'Image {i}: stream type = {type(stream_obj)}')
        if hasattr(stream_obj, 'get_data'):
            raw = stream_obj.get_data()
            print(f'  raw bytes: {len(raw)} bytes, first 50 hex: {raw[:50].hex()}')
            # Try to decode the raw bytes
            print(f'  stream metadata: {stream_obj}')
    
    # Also try pdfplumber's page.images approach - let's look at the actual streams from page objects
    print(f'\n=== Page object XObject images ===')
    # In pdfplumber, page.images returns a simple list, not individual stream access
    # Let's try with the underlying PDF
    
    # Render the full page and extract the watermark area
    page_img = page.to_image(resolution=72)
    full_img = page_img.original
    
    # Save one image from its bbox
    for i, img_info in enumerate(page.images[:1]):
        x0, top = int(img_info['x0']), int(img_info['top'])
        x1, bottom = int(img_info['x1']), int(img_info['bottom'])
        # At 72dpi, 1pt = 1px
        crop = full_img.crop((x0, top, x1, bottom))
        crop_path = 'data/processed/images/watermark_crop_test.png'
        crop.save(crop_path)
        print(f'Saved watermark candidate: {crop.size}')
        # Print some pixel colors
        pixels = crop.load()
        w, h = crop.size
        print(f'  Sample pixels (top-left 5x5):')
        for y in range(min(5, h)):
            row = []
            for x in range(min(5, w)):
                row.append(str(pixels[x, y]))
            print(f'    y={y}: {", ".join(row)}')
