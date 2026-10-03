import asyncio
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile
from mokuro.utils import InvalidImage

import reader
from dictionary import lookup

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


@app.post("/ocr")
async def ocr(image: UploadFile):
    data = await image.read()
    try:
        return await in_worker(reader.read, data)
    except InvalidImage:
        raise HTTPException(400, "That file isn't an image")


@app.get("/lookup")
def look_up(text: str, at: int):
    return lookup(text, at)


if __name__ == "__main__":
    uvicorn.run(app, port=7331)
