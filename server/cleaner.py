import sys
from pathlib import Path

import cv2
import numpy as np

SAME_COLOUR = 40
PLAIN_SHARE = 0.9
LEFTOVER = 6
OUTPUT = Path(__file__).parent / "data" / "cleaned"


def erase_block(image, mask, block):
    height, width = mask.shape
    x1, y1, x2, y2 = (int(n) for n in block.xyxy)
    font = int(block.font_size)
    pad = max(4, font // 4)
    left, top = max(0, x1 - pad), max(0, y1 - pad)
    right, bottom = min(width, x2 + pad), min(height, y2 + pad)

    grow = max(3, font // 8)
    text = cv2.dilate(mask[top:bottom, left:right], np.ones((grow, grow), np.uint8)) > 0
    region = image[top:bottom, left:right]
    around = region[~text]
    if not len(around):
        return

    colour = np.median(around, axis=0)
    if (np.abs(around - colour).max(axis=1) < SAME_COLOUR).mean() > PLAIN_SHARE:
        inside = np.zeros_like(text)
        inside[max(0, y1 - top - 2):y2 - top + 2, max(0, x1 - left - 2):x2 - left + 2] = True
        marks = np.abs(region.astype(int) - colour).max(axis=2) > LEFTOVER
        region[text | (inside & marks)] = colour
    else:
        region[:] = cv2.inpaint(region, text.astype(np.uint8) * 255, 5, cv2.INPAINT_TELEA)


def erase(image, mask, blocks):
    clean = image.copy()
    for block in blocks:
        erase_block(clean, mask, block)
    return clean


if __name__ == "__main__":
    from PIL import Image

    from reader import PageReader, find_image

    reader = PageReader()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[1:] or ["01.jpg"]:
        path = find_image(name)
        clean = reader.clean(path)
        out = OUTPUT / f"{path.stem}.png"
        cv2.imwrite(str(out), clean)
        print("Saved", out)
        Image.fromarray(cv2.cvtColor(clean, cv2.COLOR_BGR2RGB)).show()
