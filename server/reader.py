import os
import sys
import time
from pathlib import Path

import requests
from mokuro.manga_page_ocr import MangaPageOcr
from PIL import Image, ImageDraw

TEST_IMAGES = Path(__file__).parent.parent / "testimg"


def find_image(name):
    path = Path(name)
    return path if path.exists() else TEST_IMAGES / name


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


def translate(texts, key, target="EN-US"):
    host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
    response = requests.post(
        f"https://{host}/v2/translate",
        headers={"Authorization": f"DeepL-Auth-Key {key}"},
        json={
            "text": texts,
            "source_lang": "JA",
            "target_lang": target,
            "context": "\n".join(texts),
        },
        timeout=30,
    )
    response.raise_for_status()
    return [t["text"] for t in response.json()["translations"]]


def show_boxes(path, blocks):
    image = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(image)
    for number, block in enumerate(blocks, 1):
        x1, y1, x2, y2 = block["box"]
        draw.rectangle((x1, y1, x2, y2), outline="red", width=3)
        draw.text((x1, y1 - 26), str(number), fill="red", font_size=24)
    image.show()


if __name__ == "__main__":
    args = [arg for arg in sys.argv[1:] if arg != "--show"]
    path = find_image(args[0] if args else "01.jpg")
    key = os.environ.get("DEEPL_API_KEY")

    ocr = MangaPageOcr()
    start = time.time()
    blocks = read_page(ocr, path)
    print(f"\n{path.name}: {len(blocks)} text blocks in {time.time() - start:.1f}s\n")

    if key and blocks:
        translations = translate([block["text"] for block in blocks], key)
    else:
        translations = [""] * len(blocks)
        if not key:
            print("No DEEPL_API_KEY\n")

    for number, (block, english) in enumerate(zip(blocks, translations), 1):
        direction = "vertical" if block["vertical"] else "horizontal"
        print(f"{number:>3}. {direction:<10} {block['box']}  {block['text']}")
        if english:
            print(f"     -> {english}")

    if "--show" in sys.argv:
        show_boxes(path, blocks)
