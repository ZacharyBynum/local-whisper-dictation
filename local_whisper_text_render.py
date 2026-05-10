#!/usr/bin/env python3
import json
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_PATHS = (
    "/usr/share/fonts/truetype/ubuntu/UbuntuSans[wdth,wght].ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS:
        if pathlib.Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def main() -> None:
    request = json.load(sys.stdin)
    text = str(request.get("text", ""))
    width = max(1, int(request.get("width", 104)))
    height = max(1, int(request.get("height", 24)))
    size = max(8, int(request.get("size", 13)))
    color = str(request.get("color", "#f7f8fa"))

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = load_font(size)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_height = bbox[3] - bbox[1]
    y = (height - text_height) / 2 - bbox[1] - 0.5
    draw.text((0, y), text, font=font, fill=color)
    image.save(sys.stdout.buffer, format="PNG")


if __name__ == "__main__":
    main()
