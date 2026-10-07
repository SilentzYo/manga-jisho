import base64
import io
import sys
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = Path(__file__).parent / "fonts" / "ComicNeue-Bold.ttf"
OUTPUT = Path(__file__).parent / "data" / "translated"
LINE_SPACING = 1.1
MIN_SIZE = 10
SIZE_FROM_JAPANESE = 0.8
TOLERANCE = (12, 12, 12)
SOLID = 0.5
SHAPES = (0.5, 0.7, 1.0, 1.4, 2.0)
FILLED = 0.97


@dataclass
class Bubble:
    background: object
    origin: tuple = (0, 0)
    mask: object = None
    blocks: list = field(default_factory=list)

    @property
    def text(self):
        vertical = all(block["vertical"] for block in self.blocks)
        order = (lambda b: -b["box"][2]) if vertical else (lambda b: b["box"][1])
        return "".join(block["text"] for block in sorted(self.blocks, key=order))

    @property
    def font_size(self):
        return max(block["font_size"] for block in self.blocks)


@cache
def font(size):
    return ImageFont.truetype(str(FONT), size)


def flood(clean, box, reach):
    height, width = clean.shape[:2]
    x1, y1, x2, y2 = box
    left, top = max(0, x1 - reach), max(0, y1 - reach)
    right, bottom = min(width, x2 + reach), min(height, y2 + reach)

    fill = np.zeros((bottom - top + 2, right - left + 2), np.uint8)
    seed = ((x1 + x2) // 2 - left, (y1 + y2) // 2 - top)
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
    cv2.floodFill(clean[top:bottom, left:right].copy(), fill, seed, 0, TOLERANCE, TOLERANCE, flags)

    ys, xs = np.nonzero(fill[1:-1, 1:-1])
    if xs.min() == 0 or ys.min() == 0 or xs.max() == right - left - 1 or ys.max() == bottom - top - 1:
        return None
    mask = fill[1 + ys.min():2 + ys.max(), 1 + xs.min():2 + xs.max()] > 0
    return (left + xs.min(), top + ys.min()), mask


def outline(clean, box):
    x1, y1, x2, y2 = box
    size = max(x2 - x1, y2 - y1)
    for reach in (size, 2 * size, 4 * size):
        found = flood(clean, box, reach)
        if found:
            return found if found[1].mean() >= SOLID else None
    return None


def gap(a, b):
    across = max(a[0], b[0]) - min(a[2], b[2])
    down = max(a[1], b[1]) - min(a[3], b[3])
    return max(across, down, 0)


def clusters(blocks):
    groups = []
    for block in blocks:
        near = next((group for group in groups if any(
            gap(block["box"], other["box"]) <= max(block["font_size"], other["font_size"]) for other in group
        )), None)
        if near:
            near.append(block)
        else:
            groups.append([block])
    return groups


def find_bubbles(clean, blocks, backgrounds):
    regions, alone = {}, []
    for block, background in zip(blocks, backgrounds):
        found = outline(clean, block["box"]) if background is not None else None
        if found:
            origin, mask = found
            regions.setdefault((origin, mask.shape), (background, origin, mask, []))[3].append(block)
        else:
            alone.append(Bubble(background, blocks=[block]))

    bubbles = []
    for background, origin, mask, members in regions.values():
        groups = clusters(members)
        if len(groups) == 1:
            bubbles.append(Bubble(background, origin, mask, members))
        else:
            bubbles += [Bubble(background, blocks=group) for group in groups]
    return bubbles + alone


def fits_inside(integral, x1, y1, x2, y2):
    height, width = integral.shape[0] - 1, integral.shape[1] - 1
    if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
        return False
    count = integral[y2, x2] - integral[y1, x2] - integral[y2, x1] + integral[y1, x1]
    return count >= FILLED * (x2 - x1) * (y2 - y1)


def rectangles(mask):
    margin = max(3, int(min(mask.shape) * 0.08))
    inner = cv2.erode(mask.astype(np.uint8), np.ones((2 * margin + 1, 2 * margin + 1), np.uint8))
    if not inner.any():
        inner = mask.astype(np.uint8)
    ys, xs = np.nonzero(inner)
    cx, cy = int(xs.mean()), int(ys.mean())
    integral = cv2.integral(inner)

    for shape in SHAPES:
        low, high = 0, max(mask.shape)
        while low < high:
            half = (low + high + 1) // 2
            half_width = int(half * shape)
            if fits_inside(integral, cx - half_width, cy - half, cx + half_width, cy + half):
                low = half
            else:
                high = half - 1
        if low:
            yield [cx - int(low * shape), cy - low, cx + int(low * shape), cy + low]


def widen(box, width):
    x1, y1, x2, y2 = box
    wanted = max(x2 - x1, (y2 - y1) * 0.7)
    left = min(max(0, (x1 + x2) / 2 - wanted / 2), width - wanted)
    return [max(0, left), y1, min(width, left + wanted), y2]


def areas(bubble, page_width):
    xs = [n for block in bubble.blocks for n in block["box"][0::2]]
    ys = [n for block in bubble.blocks for n in block["box"][1::2]]
    text_box = [min(xs), min(ys), max(xs), max(ys)]
    if bubble.mask is None:
        return [widen(text_box, page_width)]

    left, top = bubble.origin
    inside = [[x1 + left, y1 + top, x2 + left, y2 + top] for x1, y1, x2, y2 in rectangles(bubble.mask)]
    x1, y1, x2, y2 = text_box
    if fits_inside(cv2.integral(bubble.mask.astype(np.uint8)), x1 - left, y1 - top, x2 - left, y2 - top):
        inside.append(text_box)
    return inside


def wrap(text, face, width):
    lines = []
    for word in text.split():
        if lines and face.getlength(f"{lines[-1]} {word}") <= width:
            lines[-1] += f" {word}"
        else:
            lines.append(word)
    return lines


def fit(text, area, largest):
    x1, y1, x2, y2 = area
    for size in range(max(largest, MIN_SIZE), MIN_SIZE - 1, -1):
        lines = wrap(text, font(size), x2 - x1)
        tall_enough = len(lines) * size * LINE_SPACING <= y2 - y1
        if tall_enough and all(font(size).getlength(line) <= x2 - x1 for line in lines):
            return size, lines
    return MIN_SIZE, lines


def letter(draw, area, size, lines, background):
    x1, y1, x2, y2 = area
    line_height = size * LINE_SPACING
    top = (y1 + y2) / 2 - len(lines) * line_height / 2
    if background is None:
        style = {"fill": "black", "stroke_width": max(2, size // 7), "stroke_fill": "white"}
    else:
        style = {"fill": "white" if background.mean() < 128 else "black"}
    for n, line in enumerate(lines):
        position = ((x1 + x2) / 2, top + (n + 0.5) * line_height)
        draw.text(position, line, font=font(size), anchor="mm", **style)


def typeset(clean, bubbles, translations):
    image = Image.fromarray(cv2.cvtColor(clean, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    for bubble, english in zip(bubbles, translations):
        if not english.strip():
            continue
        largest = int(bubble.font_size * SIZE_FROM_JAPANESE)
        options = [(fit(english, area, largest), area) for area in areas(bubble, clean.shape[1])]
        (size, lines), area = max(options, key=lambda option: option[0][0])
        letter(draw, area, size, lines, bubble.background)
    return image


def as_png(image):
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def as_data_url(image):
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=90)
    return "data:image/webp;base64," + base64.b64encode(buffer.getvalue()).decode()


def placeholder(japanese):
    words = "this is placeholder text because there is no DeepL key yet so you can still check the layout".split()
    return " ".join((words * 10)[:max(2, len(japanese) // 2)]).capitalize()


if __name__ == "__main__":
    from reader import PageReader, find_image
    from translator import TranslationError, translate

    reader = PageReader()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[1:] or ["01.jpg"]:
        path = find_image(name)
        page, clean, backgrounds = reader.prepare(path)
        bubbles = find_bubbles(clean, page["blocks"], backgrounds)
        japanese = [bubble.text for bubble in bubbles]
        try:
            english = translate(japanese)
        except TranslationError as error:
            print(f"{error}, using placeholder text")
            english = [placeholder(text) for text in japanese]

        for original, translated in zip(japanese, english):
            print(f"  {original}\n    -> {translated}")
        image = typeset(clean, bubbles, english)
        out = OUTPUT / f"{path.stem}.png"
        image.save(out)
        print("Saved", out)
        image.show()
