import { drawTracks } from "./overlay.js";

const canvas = document.getElementById("view");
const ctx = canvas.getContext("2d");
const placeholder = document.getElementById("placeholder");
const connPill = document.getElementById("conn");
const statsEl = document.getElementById("stats");
const carList = document.getElementById("car-list");
const carCount = document.getElementById("car-count");

const SIDEBAR_INTERVAL_MS = 250;
let lastSidebarUpdate = 0;

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.binaryType = "arraybuffer";
  ws.onopen = () => setPill("waiting for video", "warn");
  ws.onclose = () => {
    setPill("disconnected", "bad");
    setTimeout(connect, 1000);
  };
  ws.onmessage = (event) => enqueue(event.data);
}

// Only the newest message matters: if one arrives while the previous is still decoding, keep just the latest.
let busy = false;
let pending = null;

async function enqueue(buffer) {
  if (busy) {
    pending = buffer;
    return;
  }
  busy = true;
  try {
    await render(buffer);
  } finally {
    busy = false;
  }
  if (pending) {
    const next = pending;
    pending = null;
    enqueue(next);
  }
}

async function render(buffer) {
  const headerLength = new DataView(buffer).getUint32(0, true);
  const header = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 4, headerLength)));
  const jpeg = new Blob([new Uint8Array(buffer, 4 + headerLength)], { type: "image/jpeg" });
  const bitmap = await createImageBitmap(jpeg);

  if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
  }
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close();
  drawTracks(ctx, header.tracks, canvas.width / header.width);

  placeholder.hidden = true;
  updateStatus(header);
  updateSidebar(header.tracks);
}

function updateStatus({ status, latency_ms }) {
  setPill(status.connected ? "live" : "no signal", status.connected ? "ok" : "bad");
  const [w, h] = status.resolution ?? ["?", "?"];
  statsEl.textContent =
    `${w}×${h} · camera ${status.source_fps} fps · processed ${status.pipeline_fps} fps · ${latency_ms} ms`;
}

function updateSidebar(tracks) {
  const now = performance.now();
  if (now - lastSidebarUpdate < SIDEBAR_INTERVAL_MS) return;
  lastSidebarUpdate = now;

  carCount.textContent = tracks.length ? `(${tracks.length})` : "";
  carList.replaceChildren(
    ...tracks.map((track) => {
      const item = document.createElement("li");
      const [title, ...details] = track.lines ?? [`#${track.id}`];
      const id = document.createElement("div");
      id.className = "id";
      id.textContent = title;
      item.append(id, ...details.map((line) => Object.assign(document.createElement("div"), { textContent: line })));
      return item;
    }),
  );
}

function setPill(text, kind) {
  connPill.textContent = text;
  connPill.className = `pill ${kind}`;
}

connect();
