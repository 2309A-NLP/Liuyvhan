"""测 Qwen3-VL-8B-Instruct 响应时间"""
import base64, io, time, os
from openai import OpenAI

# 直接从 .env 读
import re
env_path = r"C:\Users\刘禹含\Desktop\RAG-工单04\.env"
with open(env_path, "r", encoding="utf-8") as f:
    env_content = f.read()

def get_env(key):
    m = re.search(rf"^{key}=(.+)$", env_content, re.MULTILINE)
    return m.group(1).strip() if m else ""

api_key = get_env("LLM_API_KEY")
base_url = get_env("LLM_BASE_URL")
model = "Qwen/Qwen3-VL-8B-Instruct"

client = OpenAI(api_key=api_key, base_url=base_url, timeout=30)

# 生成一张测试图片
from PIL import Image
img = Image.new("RGB", (200, 200), color=(100, 100, 200))
from PIL import ImageDraw
draw = ImageDraw.Draw(img)
draw.text((30, 80), "Test", fill="white")

buf = io.BytesIO()
img.save(buf, format="PNG")
b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

print(f"Calling {model}...", flush=True)
t0 = time.time()
try:
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            ]
        }]
    )
    elapsed = time.time() - t0
    print(f"OK ({elapsed:.1f}s): {resp.choices[0].message.content}", flush=True)
except Exception as e:
    print(f"ERROR after {time.time()-t0:.1f}s: {e}", flush=True)
