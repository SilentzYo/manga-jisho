import argparse
import asyncio
import time
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

PORT = 7331
IDLE_CHECK_SECONDS = 10
Model = Literal["accurate", "fast"]
ocr_worker = None
server = None
idle_minutes = None
last_request = time.monotonic()


def in_worker(fn, *args):
    return asyncio.get_running_loop().run_in_executor(ocr_worker, fn, *args)


async def stop_when_idle():
    while time.monotonic() - last_request < idle_minutes * 60:
        await asyncio.sleep(IDLE_CHECK_SECONDS)
    server.should_exit = True


@asynccontextmanager
async def lifespan(app):
    global ocr_worker
    with ProcessPoolExecutor(1, initializer=reader.load) as ocr_worker:
        await in_worker(reader.ready)
        watcher = asyncio.create_task(stop_when_idle()) if server and idle_minutes else None
        yield
        if watcher:
            watcher.cancel()


app = FastAPI(lifespan=lifespan, swagger_ui_parameters={"displayRequestDuration": True})


@app.middleware("http")
async def remember_activity(request, call_next):
    global last_request
    last_request = time.monotonic()
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/shutdown")
def shut_down():
    if server is None:
        raise HTTPException(409, "This server can only be stopped with Ctrl+C")
    server.should_exit = True
    return {"status": "stopping"}


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--idle", type=float, help="stop after this many minutes without requests")
    options = parser.parse_args()
    idle_minutes = options.idle
    server = uvicorn.Server(uvicorn.Config(app, port=options.port))
    server.run()
