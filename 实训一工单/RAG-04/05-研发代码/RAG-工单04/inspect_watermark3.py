"""Extract and analyze the repeated small images on page 40 (potential watermark)."""
import pdfplumber
from PIL import Image

path = 'data/raw/招股说明书2.pdf'
with pdfplumber.open(path) as pdf:
    page = pdf.pages[39]  # page 40
    
    # Extract page rendering at lower resolution
    img = page.to_image(resolution=100)
    img.save('data/processed/images/page_40_check_100.png')
    print(f'Saved page 40 render at 100dpi')

    # Pages might have the same image (duplicate) - let's check what they look like
    # by rendering the first image's bbox area
    for i, img_info in enumerate(page.images[:3]):
        x0, top, x1, bottom = img_info['x0'], img_info['top'], img_info['x1'], img_info['bottom']
        print(f'Image {i}: bbox=({x0:.0f},{top:.0f},{x1:.0f},{bottom:.0f}) size={x1-x0:.0f}x{bottom-top:.0f}')
        
        # Crop from page render
        page_img = page.to_image(resolution=200)
        cropped = page_img.original.crop((x0*2, top*2, x1*2, bottom*2))  # 200dpi = 2x pts
        crop_path = f'data/processed/images/page40_watermark_{i}.png'
        cropped.save(crop_path)
        print(f'  Saved to {crop_path}')

# Also check pages without the watermark pattern (early cover pages)
print(f'\n=== Cover page images ===')
with pdfplumber.open(path) as pdf:
    page0 = pdf.pages[0]
    print(f'Page 0: {len(page0.images)} images')
    for i, img_info in enumerate(page0.images[:3]):
        x0, top, x1, bottom = img_info['x0'], img_info['top'], img_info['x1'], img_info['bottom']
        print(f'  Image {i}: bbox=({x0:.0f},{top:.0f},{x1:.0f},{bottom:.0f}) size={x1-x0:.0f}x{bottom-top:.0f}')
