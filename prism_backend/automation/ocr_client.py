from __future__ import annotations

import base64
from typing import Optional

from openai import OpenAI

from fastapi_app.core.config import settings


def ocr_image_bytes(image_bytes: bytes, prompt: str = "识别图片中的文字，按行输出。") -> str:
    """
    OCR via SiliconFlow OpenAI-compatible endpoint.

    Note: keep API keys in environment variables; do NOT hardcode in code or docs.
    """
    if not settings.SILICONFLOW_API_KEY:
        raise RuntimeError("SILICONFLOW_API_KEY is not set")

    client = OpenAI(api_key=settings.SILICONFLOW_API_KEY, base_url=settings.SILICONFLOW_BASE_URL)
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:image/png;base64,{b64}"

    resp = client.chat.completions.create(
        model=settings.DEEPSEEK_OCR_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return (resp.choices[0].message.content or "").strip()

