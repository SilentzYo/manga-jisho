import io
import sys
import time
from pathlib import Path

import cv2
import torch
from manga_ocr.ocr import post_process
from mokuro.manga_page_ocr import MangaPageOcr
from mokuro.utils import imread
from PIL import Image, ImageDraw

from translator import TranslationError, translate

TEST_IMAGES = Path(__file__).parent.parent / "testimg"
OCR_THREADS = 6
BATCH_SIZE = 32


def find_image(name):
    path = Path(name)
    return path if path.exists() else TEST_IMAGES / name


def bounds(points):
    xs, ys = zip(*points)
    return [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]


def read_lines(texts, coords):
    lines, start = [], 0
    for text, points in zip(texts, coords):
        if text:
            lines.append({"text": text, "start": start, "box": bounds(points)})
        start += len(text)
    return lines


class PageReader:
    def __init__(self):
        torch.set_num_threads(OCR_THREADS)
        self.pages = MangaPageOcr()
        self.lines = self.pages.mocr
        self.models = {"accurate": self.lines.model}

    def model(self, name):
        if name not in self.models:
            accurate = self.models["accurate"]
            self.models[name] = torch.ao.quantization.quantize_dynamic(accurate, {torch.nn.Linear}, dtype=torch.qint8)
        return self.models[name]

    def cut(self, image, mask, block, index):
        pages = self.pages
        max_ratio = pages.max_ratio_vert if block.vertical else pages.max_ratio_hor
        chunks, _ = pages.split_into_chunks(
            image, mask, block, index, pages.text_height, max_ratio, pages.anchor_window
        )
        for chunk in chunks:
            if block.vertical:
                chunk = cv2.rotate(chunk, cv2.ROTATE_90_CLOCKWISE)
            yield Image.fromarray(chunk).convert("L").convert("RGB")

    def recognise(self, crops, model):
        texts = []
        for i in range(0, len(crops), BATCH_SIZE):
            pixels = self.lines.processor(crops[i:i + BATCH_SIZE], return_tensors="pt").pixel_values
            with torch.inference_mode():
                ids = self.model(model).generate(pixels, max_length=300)
            texts += [post_process(text) for text in self.lines.tokenizer.batch_decode(ids, skip_special_tokens=True)]
        return texts

    def read(self, path, model="accurate"):
        image = imread(path)
        _, mask, blocks = self.pages.text_detector(image, refine_mode=1, keep_undetected_mask=True)
        coords = [block.lines_array() for block in blocks]

        crops, owners = [], []
        for b, block in enumerate(blocks):
            for l in range(len(coords[b])):
                for crop in self.cut(image, mask, block, l):
                    crops.append(crop)
                    owners.append((b, l))

        texts = [[""] * len(lines) for lines in coords]
        for (b, l), text in zip(owners, self.recognise(crops, model)):
            texts[b][l] += text

        height, width = image.shape[:2]
        return {
            "width": width,
            "height": height,
            "blocks": [
                {
                    "box": [int(n) for n in block.xyxy],
                    "vertical": bool(block.vertical),
                    "text": "".join(lines),
                    "lines": read_lines(lines, block_coords),
                }
                for block, lines, block_coords in zip(blocks, texts, coords)
            ],
        }


page_reader = None


def load():
    global page_reader
    page_reader = PageReader()


def ready():
    return page_reader is not None


def read(data, model):
    return page_reader.read(io.BytesIO(data), model)


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

    reader = PageReader()
    start = time.time()
    blocks = reader.read(path)["blocks"]
    print(f"\n{path.name}: {len(blocks)} text blocks in {time.time() - start:.1f}s\n")

    try:
        translations = translate([block["text"] for block in blocks])
    except TranslationError as error:
        translations = [""] * len(blocks)
        print(error, "\n")

    for number, (block, english) in enumerate(zip(blocks, translations), 1):
        direction = "vertical" if block["vertical"] else "horizontal"
        print(f"{number:>3}. {direction:<10} {block['box']}  {block['text']}")
        if english:
            print(f"     -> {english}")

    if "--show" in sys.argv:
        show_boxes(path, blocks)
