from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Optional

import httpx
from openai import OpenAI

from fastapi_app.core.config import settings


def _data_url_png(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def aspect_ratio_to_image_size(aspect_ratio: str) -> str:
    # SiliconFlow `image_size` format varies by model; keep common WxH strings.
    mapping = {
        # SiliconFlow Qwen-Image-Edit currently supports these two defaults.
        "3:4": "1140x1472",
        "4:3": "1472x1140",
    }
    return mapping.get(aspect_ratio, "1140x1472")


def build_unified_cover_prompt(
    *,
    platform_name: str,
    aspect_ratio: str = "3:4",
    extra_style: str = "",
) -> str:
    # 该 prompt 用于图生图（输入首帧 + prompt），目标是做“封面海报化”而不是纯文生图。
    base = (
        f"基于输入图片（视频首帧），制作一张符合「{platform_name}」风格的短视频封面海报。\n"
        "要求：\n"
        "1) 保留画面主体与核心动作（不要换人、不要改服装风格到不一致），提升质感与清晰度；\n"
        f"2) 构图比例为 {aspect_ratio}，主体居中偏上，留出文字安全区（顶部/底部边距）；\n"
        "3) 画面风格“商业海报级”：色彩统一、高级感、对比度适中、光影自然、背景适度虚化且干净；\n"
        "4) 默认不添加任何长句文字/水印/平台 Logo/乱码；如需要标题，仅添加 4-8 个汉字的短标题，字体清晰高级，不遮挡主体；\n"
        "5) 去除压缩块/噪点/锯齿/重影，边缘干净，细节自然，不要过曝、不要脏乱。\n"
        "输出：一张可直接用于发布的成品封面。"
    )
    if extra_style.strip():
        base += f"\n额外风格要求：{extra_style.strip()}"
    return base


def build_prompt_from_image(
    image_bytes: bytes,
    *,
    platform_name: str,
    aspect_ratio: str = "3:4",
    style_hint: str = "",
) -> str:
    """
    Use a vision-capable chat model to produce a high-quality generation prompt.
    Falls back to a deterministic template if the model is not configured.
    """
    model = (settings.SILICONFLOW_PROMPT_MODEL or "").strip()
    if not settings.SILICONFLOW_API_KEY or not model:
        return build_unified_cover_prompt(
            platform_name=platform_name,
            aspect_ratio=aspect_ratio,
            extra_style=style_hint,
        )

    client = OpenAI(api_key=settings.SILICONFLOW_API_KEY, base_url=settings.SILICONFLOW_BASE_URL)
    data_url = _data_url_png(image_bytes)

    sys_prompt = (
        "你是资深短视频封面海报的提示词工程师。"
        "请基于输入图片内容，输出一个适用于图生图（封面海报化）的中文 prompt。"
        "注意：不要生成长句文字/水印/平台logo；如需标题，最多 4-8 个汉字。"
        "只输出 prompt 本身，不要解释，不要加引号。"
    )
    user_prompt = (
        f"平台：{platform_name}\n"
        f"目标封面比例：{aspect_ratio}\n"
        f"风格补充：{style_hint or '无'}\n"
        "请输出：符合平台视觉趋势、清晰、主体突出、排版合理、可包含标题文字的封面prompt。"
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": user_prompt},
                ],
            },
        ],
    )
    return (resp.choices[0].message.content or "").strip() or build_unified_cover_prompt(
        platform_name=platform_name,
        aspect_ratio=aspect_ratio,
        extra_style=style_hint,
    )


@dataclass(frozen=True)
class ImageGenerationResult:
    prompt: str
    image_bytes: bytes
    content_type: str
    raw_url: Optional[str] = None


async def generate_cover_image(
    *,
    image_bytes: bytes,
    prompt: str,
    aspect_ratio: str,
    negative_prompt: str = "",
    seed: int = 499999999,
    num_inference_steps: int = 20,
    guidance_scale: float = 7.5,
    cfg: float = 10.05,
) -> ImageGenerationResult:
    if not settings.SILICONFLOW_API_KEY:
        raise RuntimeError("SILICONFLOW_API_KEY is not set")

    url = settings.SILICONFLOW_BASE_URL.rstrip("/") + "/images/generations"
    default_negative = (
        "低清晰度, 低分辨率, 模糊, 噪点, 锯齿, 压缩块, 重影, 过曝, 欠曝, "
        "水印, 平台logo, 二维码, 网址, 署名, 乱码文字, 长句字幕, 边框, "
        "畸形手, 多余肢体, 人脸崩坏, 变形, 裸露, NSFW"
    )
    payload = {
        "model": settings.SILICONFLOW_IMAGE_MODEL,
        "prompt": prompt,
        "negative_prompt": negative_prompt or default_negative,
        "image_size": aspect_ratio_to_image_size(aspect_ratio),
        "batch_size": 1,
        "seed": seed,
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
        "cfg": cfg,
        "image": _data_url_png(image_bytes),
    }

    headers = {
        "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

        # SiliconFlow returns images as urls in most cases.
        images = data.get("images") or data.get("data") or []
        first = images[0] if images else None
        if isinstance(first, dict):
            if first.get("b64_json"):
                img = base64.b64decode(first["b64_json"])
                return ImageGenerationResult(prompt=prompt, image_bytes=img, content_type="image/png")
            if first.get("url"):
                img_url = first["url"]
                r2 = await client.get(img_url)
                r2.raise_for_status()
                return ImageGenerationResult(
                    prompt=prompt,
                    image_bytes=r2.content,
                    content_type=r2.headers.get("content-type", "image/png"),
                    raw_url=img_url,
                )

        raise RuntimeError(f"Unexpected images response: keys={list(data.keys())}")
