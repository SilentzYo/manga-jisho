import asyncio
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from typing import Literal

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Response, UploadFile
from mokuro.utils import InvalidImage
from pydantic import BaseModel

import reader
import translator
from dictionary import lookup
from typesetter import as_data_url, as_png, find_bubbles, typeset

Model = Literal["accurate", "fast"]
ocr_worker = None


def in_worker(fn, *args):
    return asyncio.get_running_loop().run_in_executor(ocr_worker, fn, *args)


@asynccontextmanager
async def lifespan(app):
    global ocr_worker
    with ProcessPoolExecutor(1, initializer=reader.load) as ocr_worker:
        await in_worker(reader.ready)
        yield


app = FastAPI(lifespan=lifespan, swagger_ui_parameters={"displayRequestDuration": True})


async def on_image(image, fn, *args):
    data = await image.read()
    try:
        return await in_worker(fn, data, *args)
    except InvalidImage:
        raise HTTPException(400, "That file isn't an image")


async def in_english(page, clean, backgrounds, key):
    bubbles = await asyncio.to_thread(find_bubbles, clean, page["blocks"], backgrounds)
    english = await asyncio.to_thread(translator.translate, [bubble.text for bubble in bubbles], key)
    return await asyncio.to_thread(typeset, clean, bubbles, english)


@app.post("/ocr")
async def ocr(
    image: UploadFile,
    model: Model = "accurate",
    translate: bool = Form(False),
    key: str | None = Form(None),
):
    if not translate:
        return await on_image(image, reader.read, model)

    page, clean, backgrounds = await on_image(image, reader.prepare, model)
    try:
        picture = await in_english(page, clean, backgrounds, key)
        page["translated"] = await asyncio.to_thread(as_data_url, picture)
    except translator.TranslationError as error:
        page["translation_error"] = str(error)
    return page


@app.post("/clean")
async def clean(image: UploadFile):
    return Response(await on_image(image, reader.clean), media_type="image/png")


@app.get("/lookup")
def look_up(text: str, at: int):
    return lookup(text, at)


class Translation(BaseModel):
    texts: list[str]
    target: str = translator.TARGET
    key: str | None = None


@app.post("/translate")
def translate_texts(request: Translation):
    try:
        return {"translations": translator.translate(request.texts, request.key, request.target)}
    except translator.TranslationError as error:
        raise HTTPException(502, str(error))


@app.post("/translate-page")
async def translate_page(image: UploadFile, model: Model = "accurate", key: str | None = Form(None)):
    page, clean, backgrounds = await on_image(image, reader.prepare, model)
    try:
        picture = await in_english(page, clean, backgrounds, key)
    except translator.TranslationError as error:
        raise HTTPException(502, str(error))
    return Response(as_png(picture), media_type="image/png")


if __name__ == "__main__":
    uvicorn.run(app, port=7331)
