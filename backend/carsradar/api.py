"""HTTP + WebSocket server: streams frames with their track overlays to the browser."""

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIR, Settings
from .ingest import VideoSource
from .pipeline import Pipeline, Result


def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        source = VideoSource(settings.source, loop_file=settings.loop_file)
        pipeline = Pipeline(source, settings)
        source.start()
        pipeline.start()
        app.state.source = source
        app.state.pipeline = pipeline
        yield
        pipeline.stop()
        source.stop()

    app = FastAPI(title="Cars Radar", lifespan=lifespan)

    @app.get("/api/status")
    def status() -> dict:
        return _status(app.state.source, app.state.pipeline)

    @app.websocket("/ws")
    async def stream(ws: WebSocket) -> None:
        await ws.accept()
        sender = asyncio.create_task(_send_results(ws, ws.app.state.source, ws.app.state.pipeline))
        try:
            # The client doesn't send anything yet; receiving is how we notice it went away.
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            sender.cancel()

    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


async def _send_results(ws: WebSocket, source: VideoSource, pipeline: Pipeline) -> None:
    last_index = 0
    while True:
        result = await asyncio.to_thread(pipeline.results.wait_newer, last_index, 1.0)
        if result is None:
            continue
        last_index = result.index
        await ws.send_bytes(pack_result(result, _status(source, pipeline)))


def pack_result(result: Result, status: dict) -> bytes:
    """Binary message: 4-byte little-endian header length, JSON header, then the JPEG bytes."""
    header = json.dumps(
        {
            "index": result.index,
            "pts": result.pts,
            "width": result.width,
            "height": result.height,
            "tracks": result.tracks,
            "latency_ms": round(result.latency_ms, 1),
            "status": status,
        }
    ).encode()
    return len(header).to_bytes(4, "little") + header + result.jpeg


def _status(source: VideoSource, pipeline: Pipeline) -> dict:
    return {
        "source": source.url,
        "connected": source.connected,
        "resolution": source.resolution,
        "source_fps": round(source.fps.rate, 1),
        "pipeline_fps": round(pipeline.fps.rate, 1),
    }
