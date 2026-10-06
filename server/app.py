import asyncio
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from typing import Literal

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Response, UploadFile
from mokuro.utils import InvalidImage
from pydantic import BaseModel

import reader
from dictionary import lookup
from translator import TARGET, TranslationError, translate
from typesetter import as_png, find_bubbles, typeset

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


@app.post("/ocr")
async def ocr(image: UploadFile, model: Literal["accurate", "fast"] = "accurate"):
    return await on_image(image, reader.read, model)


@app.post("/clean")
async def clean(image: UploadFile):
    return Response(await on_image(image, reader.clean), media_type="image/png")


@app.get("/lookup")
def look_up(text: str, at: int):
    return lookup(text, at)


class Translation(BaseModel):
    texts: list[str]
    target: str = TARGET
    key: str | None = None


@app.post("/translate")
def translate_texts(request: Translation):
    try:
        return {"translations": translate(request.texts, request.key, request.target)}
    except TranslationError as error:
        raise HTTPException(502, str(error))


@app.post("/translate-page")
async def translate_page(
    image: UploadFile,
    model: Literal["accurate", "fast"] = "accurate",
    key: str | None = Form(None),
):
    page, clean, backgrounds = await on_image(image, reader.prepare, model)
    bubbles = await asyncio.to_thread(find_bubbles, clean, page["blocks"], backgrounds)
    try:
        english = await asyncio.to_thread(translate, [bubble.text for bubble in bubbles], key)
    except TranslationError as error:
        raise HTTPException(502, str(error))
    picture = await asyncio.to_thread(typeset, clean, bubbles, english)
    return Response(as_png(picture), media_type="image/png")


if __name__ == "__main__":
    uvicorn.run(app, port=7331)
