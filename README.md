# Cars Radar

Live vehicle detection and tracking on an iPhone telephoto feed, shown in the browser with a box following each car. Everything runs locally on a Windows laptop.

```
iPhone (Blackmagic Camera) ──SRT/RTMP──▶ MediaMTX ──RTSP──▶ Python backend ──WebSocket──▶ browser
                                          (relay)           YOLO26 + ByteTrack            canvas + overlay
```

The long-term goal is to label each car with its plate, color, make/model and approximate speed. Today the system detects and tracks vehicles; the other labels are on the roadmap below.

## Features

- **Live ingest.** Reads the phone's stream through MediaMTX, or plays a recorded clip at real-time pace (looped by default). Live streams reconnect automatically.
- **Vehicle detection.** Ultralytics YOLO26 finds cars, motorcycles, buses and trucks on full-resolution frames. An optional region of interest crops the frame to the road, so more of the model's input pixels land on cars.
- **Stable tracking.** ByteTrack assigns IDs. Boxes come straight from the detector, not from the tracker's Kalman estimate, so they don't trail behind fast cars. A track only appears after 3 detections, which hides one-frame false positives. The vehicle class is a majority vote over the whole track. A car hidden for up to about 2 seconds keeps its ID.
- **Low-latency view.** Every stage keeps only the newest frame, so a slow consumer skips frames instead of falling behind. The browser shows the downscaled frame, green boxes with labels, a list of cars in view, and live stats: resolution, camera fps, processed fps and latency.
- **GPU or CPU.** The detector runs on CUDA when an NVIDIA GPU is available and falls back to the CPU otherwise.

### Roadmap

- Done: live ingest (phone or clip), car detection and tracking with stable IDs, browser view.
- Next: calibration and speed (phase 3), color and make/model (phase 4), plates (phase 5).

## Architecture

| Part | What it does |
| --- | --- |
| `phone/` | A Blackmagic Camera custom streaming service (`CarsRadar.xml`). The iPhone publishes to MediaMTX path `live/cam` over SRT (lower delay) or RTMP (more compatible). |
| `mediamtx/` | Config for [MediaMTX](https://github.com/bluenviron/mediamtx), a stream relay. It accepts SRT on `:8890` and RTMP on `:1935`, and re-serves the stream as RTSP (TCP) on `:8554`. It can optionally record the raw stream. |
| `backend/` | The `carsradar` Python package. A decode thread (PyAV/FFmpeg) reads RTSP, SRT or a file. A pipeline thread runs YOLO26 + ByteTrack and encodes a display JPEG. FastAPI serves the frontend and streams results. |
| `frontend/` | Plain HTML, CSS and JavaScript with no build step. It draws each frame and overlay on a `<canvas>`. The backend serves it at `/`. |
| `scripts/` | `publish_clip.py` pushes a recorded clip into MediaMTX in real time, standing in for the phone. |

**Backend endpoints**

- `GET /api/status`: source URL, connection state, resolution, source and pipeline fps.
- `WS /ws`: one binary message per processed frame. Each message is a 4-byte little-endian header length, then a JSON header (frame index, timestamp, full-resolution size, tracks, latency, status), then the JPEG bytes. Track boxes are in full-resolution pixel coordinates.

## Tech stack

- **Backend:** Python 3.12, [uv](https://docs.astral.sh/uv/), FastAPI + Uvicorn, PyAV, OpenCV, NumPy, pydantic-settings.
- **ML:** PyTorch (CUDA 12.8 wheels) and [Ultralytics](https://github.com/ultralytics/ultralytics) YOLO26, with Ultralytics' ByteTrack implementation.
- **Streaming:** MediaMTX (SRT/RTMP in, RTSP out).
- **Frontend:** vanilla JavaScript (ES modules) and Canvas 2D.
- **Camera:** iPhone with the free Blackmagic Camera app.

## Prerequisites

- Windows 10/11. The commands below are PowerShell, and the backend itself is plain Python.
- [uv](https://docs.astral.sh/uv/getting-started/installation/). It installs Python 3.12 for you if needed.
- An NVIDIA GPU with a current driver is strongly recommended. The project pins PyTorch's CUDA 12.8 builds, which RTX 50-series (Blackwell) cards require. The CPU fallback works but is slow.
- For the live phone feed: an iPhone with [Blackmagic Camera](https://apps.apple.com/app/blackmagic-camera/id6449580241) and the MediaMTX binary (see below). Both phone and laptop must be on the same Wi-Fi.
- Optional: [VLC](https://www.videolan.org/) to check the stream.

## External downloads

These files are not in the repository.

| What | Where to get it | Expected path |
| --- | --- | --- |
| MediaMTX binary | [github.com/bluenviron/mediamtx/releases](https://github.com/bluenviron/mediamtx/releases). Download the `windows_amd64` zip; the config targets v1.21. | `mediamtx/mediamtx.exe` |
| YOLO26 weights (`yolo26s.pt`) | Downloaded automatically by Ultralytics on the first run. To fetch them manually, see the [Ultralytics YOLO26 docs](https://docs.ultralytics.com/models/yolo26/). | `data/models/yolo26s.pt` |
| Test clips (optional) | Your own street recordings, for example from the phone. | `data/clips/*.mp4` |

When you extract the MediaMTX zip, copy only `mediamtx.exe`. The zip also contains a default `mediamtx.yml`, which would overwrite this repo's config.

## Setup

```powershell
git clone https://github.com/MohammadAlMokdad/Cars-Radar.git
cd Cars-Radar\backend
uv sync          # creates backend\.venv with Python 3.12 and CUDA 12.8 PyTorch
```

Then put `mediamtx.exe` in `mediamtx\` (see [External downloads](#external-downloads)). If you want to change any settings, copy `.env.example` to `.env` at the repo root.

## Run

```powershell
# Terminal 1: stream relay
cd mediamtx
.\mediamtx.exe mediamtx.yml

# Terminal 2: backend
cd backend
uv run carsradar
```

Open http://localhost:8000. The page shows "waiting for video" until frames arrive. While the stream is missing, the backend retries every 2 seconds.

**Without the phone**

- Play a clip directly, without MediaMTX: `uv run carsradar --source ..\data\clips\your-clip.mp4`
- Or replay a clip through MediaMTX, exactly as the phone would send it:

  ```powershell
  # with MediaMTX running, from backend\
  uv run python ..\scripts\publish_clip.py ..\data\clips\your-clip.mp4   # add --once to stop at the end
  uv run carsradar
  ```

## Configuration

The backend reads settings from three places, highest priority first: CLI flags (`--source`, `--host`, `--port`), `CARSRADAR_<NAME>` environment variables, and a `.env` file at the repo root. [.env.example](.env.example) lists every setting.

| Variable | Default | Meaning |
| --- | --- | --- |
| `CARSRADAR_SOURCE` | `rtsp://127.0.0.1:8554/live/cam` | `rtsp://` or `srt://` URL, or a path to a video file |
| `CARSRADAR_LOOP_FILE` | `true` | Loop a file source instead of stopping at its end |
| `CARSRADAR_HOST` | `127.0.0.1` | Web server bind address (`0.0.0.0` to allow other devices) |
| `CARSRADAR_PORT` | `8000` | Web server port |
| `CARSRADAR_DISPLAY_WIDTH` | `1600` | Width of the JPEG sent to the browser (detection always uses full resolution) |
| `CARSRADAR_JPEG_QUALITY` | `80` | Display JPEG quality |
| `CARSRADAR_MODEL` | `yolo26s.pt` | Detector weights in `data/models/`; for example, `yolo26m.pt` is more accurate but slower |
| `CARSRADAR_IMGSZ` | `1280` | Detector input size |
| `CARSRADAR_CONF` | `0.25` | Detection confidence threshold |
| `CARSRADAR_ROI` | unset (whole frame) | Road region as frame fractions, for example `[0, 0.35, 1, 0.8]` |

You can tune tracker settings in [backend/carsradar/bytetrack.yaml](backend/carsradar/bytetrack.yaml).

**Ports**

| Port | Protocol | Used by |
| --- | --- | --- |
| 8000 | TCP | Backend web UI, `/api/status` and `/ws` |
| 8554 | TCP | MediaMTX RTSP (the backend, VLC and the clip publisher connect here) |
| 8890 | UDP | MediaMTX SRT (the phone publishes here) |
| 1935 | TCP | MediaMTX RTMP (the phone publishes here) |

**Recording.** To keep the raw phone stream for offline re-processing, set `record: true` in [mediamtx/mediamtx.yml](mediamtx/mediamtx.yml). MediaMTX then writes 10-minute segments to `data/recordings/` and deletes them after 7 days.

## Phone setup

1. **Mount the phone rigidly** on a tripod or a window clamp. Speed measurement assumes the camera never moves.
2. **Set up Blackmagic Camera.** Menu names may differ between app versions.
   - Lens: telephoto, zoomed to **8x**. This gives the most real detail; zooming past 8x only enlarges pixels.
   - Format: 4K, 30 fps, HEVC.
   - **Shutter: 1/1000 s** (1/2000 s in strong sun). Slower shutters blur moving plates.
   - ISO: auto, or as low as the light allows.
   - Lock focus on the street, lock white balance, and turn stabilization off.
3. **Stream to the laptop.** Blackmagic Camera only accepts custom servers as an imported XML file. Its "Stream Router" option is Blackmagic's paid cloud service and isn't used here.
   - Edit [phone/CarsRadar.xml](phone/CarsRadar.xml) so that both server URLs point to your laptop's Wi-Fi IP (check with `ipconfig`). The file defines a "Cars Radar Laptop" service with two servers:
     - **Laptop SRT** sends to `srt://<LAPTOP_IP>:8890?streamid=publish:live/cam`. It has the lower delay.
     - **Laptop RTMP** sends to `rtmp://<LAPTOP_IP>:1935/live` with stream key `cam`. It adds 1 to 3 seconds of delay but is the most compatible.
   - Send the file to the iPhone by AirDrop, iCloud Drive or a message to yourself. Then open it and share it to Blackmagic Camera, or use the import option under Settings > Live Stream.
   - Choose the **Cars Radar Laptop** service, a server, and the **4K Max** quality preset.
   - Put the phone and laptop on the same Wi-Fi, 5 GHz if possible. When Windows asks, allow MediaMTX through Windows Firewall on private networks.
4. **Check the stream.** Open `rtsp://127.0.0.1:8554/live/cam` in VLC (Media > Open Network Stream), then run `uv run carsradar`.
5. **Record test clips.** Record 3 to 5 one-minute 4K clips in daylight at 4x and at 8x, covering each street you can see. Copy them to `data/clips/`. They are the test set for calibration, plates and make/model.

## Tests

```powershell
cd backend
uv run pytest
```

The tests cover the frame mailbox, ROI cropping, track registry rules and the WebSocket message layout. They don't need a GPU, a stream or model weights.

## Project structure

```
backend/
  carsradar/
    main.py          CLI entry point (uv run carsradar)
    config.py        settings (env vars, .env, CLI)
    ingest.py        video decoding thread (stream or file)
    detector.py      YOLO26 detection + ByteTrack IDs, ROI crop
    tracks.py        per-car state across frames
    pipeline.py      processing loop, display JPEG
    api.py           FastAPI app: static frontend, /api/status, /ws
    bytetrack.yaml   tracker settings
  tests/             pytest unit tests
  pyproject.toml     dependencies (uv)
  uv.lock
frontend/            index.html, app.js, overlay.js, styles.css
mediamtx/            mediamtx.yml (binary downloaded separately)
phone/               CarsRadar.xml, Blackmagic Camera streaming service
scripts/             publish_clip.py
data/                created locally, git-ignored: models/, clips/, recordings/
```

## Privacy

This tool films public streets, so it can capture license plates and people. Clips, recordings and model files stay on your machine; `data/` is git-ignored. Check the local rules on recording in public before you use it.

## Credits and licenses

- [Ultralytics](https://github.com/ultralytics/ultralytics) provides YOLO26 and the ByteTrack implementation. It is AGPL-3.0, or an Ultralytics Enterprise License. The pretrained weights are downloaded separately and fall under the same terms.
- ByteTrack: Zhang et al., "ByteTrack: Multi-Object Tracking by Associating Every Detection Box", ECCV 2022.
- [MediaMTX](https://github.com/bluenviron/mediamtx) is MIT-licensed. It is not redistributed here.
- Other dependencies: [PyAV](https://github.com/PyAV-Org/PyAV), [FastAPI](https://fastapi.tiangolo.com/), [OpenCV](https://opencv.org/), [PyTorch](https://pytorch.org/).
- Blackmagic Camera is an app by Blackmagic Design. This project is not affiliated with Blackmagic Design.
