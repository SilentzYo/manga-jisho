from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile
from mokuro.manga_page_ocr import MangaPageOcr
from mokuro.utils import InvalidImage

from reader import read_page

models = {}


@asynccontextmanager
async def lifespan(app):
    models["ocr"] = MangaPageOcr()
    yield


app = FastAPI(lifespan=lifespan, swagger_ui_parameters={"displayRequestDuration": True})


@app.post("/ocr")
def ocr(image: UploadFile):
    try:
        blocks = read_page(models["ocr"], image.file)
    except InvalidImage:
        raise HTTPException(400, "That file isn't an image")
    return {"blocks": blocks}


if __name__ == "__main__":
    uvicorn.run(app, port=7331)
