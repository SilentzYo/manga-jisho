from contextlib import asynccontextmanager
from threading import Lock

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile
from mokuro.manga_page_ocr import MangaPageOcr
from mokuro.utils import InvalidImage

from dictionary import lookup
from reader import read_page
from words import tokenize

models = {}
lock = Lock()


@asynccontextmanager
async def lifespan(app):
    models["ocr"] = MangaPageOcr()
    yield


app = FastAPI(lifespan=lifespan, swagger_ui_parameters={"displayRequestDuration": True})


@app.post("/ocr")
def ocr(image: UploadFile):
    try:
        with lock:
            page = read_page(models["ocr"], image.file)
    except InvalidImage:
        raise HTTPException(400, "That file isn't an image")
    for block in page["blocks"]:
        block["tokens"] = tokenize(block["text"])
    return page


@app.get("/lookup")
def look_up(text: str, at: int):
    return lookup(text, at)


if __name__ == "__main__":
    uvicorn.run(app, port=7331)
