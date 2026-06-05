import sys
sys.path.insert(0, r"C:\Users\刘禹含\Desktop\RAG-工单04")
from app.core.config import settings
from openai import OpenAI
import base64, io
from PIL import Image, ImageDraw

img = Image.new("RGB", (100, 100), color="white")
draw = ImageDraw.Draw(img)
draw.rectangle([10, 10, 90, 90], outline="black")
draw.text((30, 40), "ABC", fill="black")
buffer = io.BytesIO()
img.save(buffer, format="PNG")
img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

models = [
    "THUDM/GLM-4.1V-9B-Thinking",
    "Qwen/Qwen2.5-VL-7B-Instruct",
]

for model in models:
    print(f"Testing: {model} ", end="", flush=True)
    try:
        response = client.chat.completions.create(
            model=model, temperature=0, timeout=30,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "What is in this image? Answer in one word."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            ]}],
        )
        answer = response.choices[0].message.content.strip()
        print(f"- OK: {answer[:60]}")
    except Exception as e:
        err = str(e)
        if "20012" in err:
            print("- NOT FOUND (model does not exist)")
        else:
            print(f"- ERROR: {err[:80]}")
