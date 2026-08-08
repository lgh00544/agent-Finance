"""
MiniMax 多模态链路快速验证:
1. 检查 .env 中 MiniMax 配置
2. 生成一张带文字的测试图片
3. 调用 MiniMax M3 图片理解,验证识别结果
用法: .venv/Scripts/python backend/scripts/minimax_check.py
"""
import sys
import time

sys.path.insert(0, ".")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.core.config import settings
from app.services.multimodal import get_multimodal_client

# 生成测试图片:白底 + 大号黑字,验证模型真实读图能力
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[失败] 缺少 Pillow,无法生成测试图片,跳过")
    sys.exit(1)


def make_test_image() -> bytes:
    img = Image.new("RGB", (400, 120), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font = ImageFont.load_default()
    draw.text((20, 30), "SELL 12345", fill="black", font=font)
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main() -> int:
    print("=" * 50)
    print("1. MiniMax 配置检查 (.env)")
    print("=" * 50)
    for label, val in [
        ("MINIMAX_ENABLE", settings.minimax_enable),
        ("MINIMAX_API_KEY", settings.minimax_api_key),
        ("MINIMAX_BASE_URL", settings.minimax_base_url),
        ("MINIMAX_MODEL", settings.minimax_model),
        ("MINIMAX_OCR_ENABLE", settings.minimax_ocr_enable),
    ]:
        shown = f"{str(val)[:8]}..." if label == "MINIMAX_API_KEY" and val else val
        print(f"  [{'OK' if val else '缺失'}]   {label} = {shown}")

    if not settings.minimax_enable:
        print("\nMINIMAX_ENABLE=false,多模态能力默认关闭,无需验证")
        return 0
    if not settings.minimax_api_key:
        print("\n[失败] MINIMAX_ENABLE=true 但未配置 MINIMAX_API_KEY")
        return 1

    print("\n" + "=" * 50)
    print("2. MiniMax M3 图片理解验证")
    print("=" * 50)
    client = get_multimodal_client()
    if client is None:
        print("[失败] 多模态客户端装配失败(检查 MINIMAX_ENABLE / API_KEY)")
        return 1

    image_bytes = make_test_image()
    print(f"  -> 生成测试图片 {len(image_bytes) / 1024:.1f}KB(内容: SELL 12345)")
    t0 = time.time()
    try:
        text = client.analyze_image(
            image_bytes,
            "这张图片上的文字是什么?只输出文字内容本身,不要解释。",
        )
        cost = time.time() - t0
        print(f"  [OK] 调用成功,耗时 {cost:.1f}s")
        print(f"       识别结果: {text!r}")
        # 校验是否读出了图片上的文字(允许大小写/空格差异)
        normalized = text.lower().replace(" ", "").replace("\n", "")
        if "sell" in normalized or "12345" in normalized:
            print("\n结论: MiniMax 多模态链路正常,能真实读取图片内容 ✅")
            return 0
        print("\n[警告] 调用成功但识别内容与测试图不符(可能文字渲染/识别差异),建议人工核对")
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"  [失败] {type(e).__name__}: {e}")
        print("\n结论: MiniMax 调用失败 ❌")
        return 3


if __name__ == "__main__":
    sys.exit(main())
