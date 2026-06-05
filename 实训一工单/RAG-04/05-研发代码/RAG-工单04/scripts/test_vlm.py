"""测试 SiliconFlow 上可用的视觉模型"""
import sys
sys.path.insert(0, r"C:\Users\刘禹含\Desktop\RAG-工单04")
from app.core.config import settings
from openai import OpenAI

import base64
import io
from PIL import Image, ImageDraw

# 创建测试图片
img = Image.new("RGB", (100, 100), color="white")
draw = ImageDraw.Draw(img)
draw.rectangle([10, 10, 90, 90], outline="black")
draw.text((30, 40), "ABC", fill="black")
buffer = io.BytesIO()
img.save(buffer, format="PNG")
img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

models_to_try = [
    "zai-org/GLM-4.1V-9B-Thinking",
    "THUDM/GLM-4.1V-9B-Thinking",
    "Qwen/Qwen2.5-VL-7B-Instruct",
    "Qwen/Qwen2.5-VL-72B-Instruct",
    "deepseek-ai/deepseek-vl2",
]

for model in models_to_try:
    print(f"尝试: {model}...", end=" ", flush=True)
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            timeout=15,
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": "简短回答：图中有什么？"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                ]},
            ],
        )
        print(f"✓ 成功! 回答: {response.choices[0].message.content[:80]}")
    except Exception as e:
        msg = str(e)
        if "400" in msg:
            print(f"✗ 404 (模型不存在)")
        elif "401" in msg or "402" in msg:
            print(f"✗ 鉴权/余额不足)")
        elif "timeout" in msg.lower():
            print(f"✗ 超时")
        else:
            print(f"✗ {msg[:60]}")
