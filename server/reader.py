import sys
import time
from pathlib import Path

from mokuro.manga_page_ocr import MangaPageOcr
from PIL import Image, ImageDraw

TEST_IMAGES = Path(__file__).parent.parent / "testimg"
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp"}


def read_page(ocr, path):
    page = ocr(path)
    return [
        {
            "box": [int(n) for n in block["box"]],
            "vertical": bool(block["vertical"]),
            "text": "".join(block["lines"]),
        }
        for block in page["blocks"]
    ]


def show_boxes(path, blocks):
    image = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(image)
    for number, block in enumerate(blocks, 1):
        x1, y1, x2, y2 = block["box"]
        draw.rectangle((x1, y1, x2, y2), outline="red", width=3)
        draw.text((x1, y1 - 26), str(number), fill="red", font_size=24)
    image.show()


if __name__ == "__main__":
    paths = [Path(arg) for arg in sys.argv[1:] if arg != "--show"]
    if not paths:
        paths = sorted(p for p in TEST_IMAGES.iterdir() if p.suffix.lower() in IMAGE_TYPES)
    ocr = MangaPageOcr()

    for path in paths:
        start = time.time()
        blocks = read_page(ocr, path)
        print(f"\n{path.name}: {len(blocks)} text blocks in {time.time() - start:.1f}s")

        for number, block in enumerate(blocks, 1):
            direction = "vertical" if block["vertical"] else "horizontal"
            print(f"{number:>3}. {direction:<10} {block['box']}  {block['text']}")

        if "--show" in sys.argv:
            show_boxes(path, blocks)
