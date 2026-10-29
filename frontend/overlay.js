// Draws track boxes and their label lines on top of the frame already painted on the canvas.
// Track boxes arrive in full-resolution frame coordinates; `scale` maps them to canvas pixels.

const BOX_COLOR = "#2bff88";
const LABEL_BG = "rgba(0, 0, 0, 0.7)";

export function drawTracks(ctx, tracks, scale) {
  const lineWidth = Math.max(2, ctx.canvas.width / 600);
  const fontSize = Math.max(12, Math.round(ctx.canvas.width / 90));
  ctx.font = `600 ${fontSize}px "Segoe UI", system-ui, sans-serif`;
  ctx.textBaseline = "top";

  for (const track of tracks) {
    const [x1, y1, x2, y2] = track.box.map((v) => v * scale);
    ctx.strokeStyle = BOX_COLOR;
    ctx.lineWidth = lineWidth;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    drawLabel(ctx, track.lines ?? [`#${track.id}`], x1, y1, y2, fontSize);
  }
}

function drawLabel(ctx, lines, x, boxTop, boxBottom, fontSize) {
  const pad = Math.round(fontSize * 0.3);
  const lineHeight = Math.round(fontSize * 1.25);
  const width = Math.max(...lines.map((l) => ctx.measureText(l).width)) + pad * 2;
  const height = lines.length * lineHeight + pad * 2;

  // Prefer above the box; fall back to below it near the top edge of the frame.
  let y = boxTop - height - 2;
  if (y < 0) y = boxBottom + 2;
  x = Math.min(Math.max(0, x), ctx.canvas.width - width);

  ctx.fillStyle = LABEL_BG;
  ctx.fillRect(x, y, width, height);
  ctx.fillStyle = BOX_COLOR;
  lines.forEach((line, i) => ctx.fillText(line, x + pad, y + pad + i * lineHeight));
}
