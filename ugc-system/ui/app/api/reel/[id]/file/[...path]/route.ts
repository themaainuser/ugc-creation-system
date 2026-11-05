import { promises as fs } from "node:fs";
import path from "node:path";
import { jobPath, validId } from "../../../../../../lib/reel-server";

export const runtime = "nodejs";
const TYPES: Record<string, string> = {
  ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
  ".mp4": "video/mp4", ".mov": "video/quicktime", ".m4v": "video/mp4", ".webm": "video/webm",
  ".md": "text/markdown; charset=utf-8", ".json": "application/json; charset=utf-8",
};
const ALLOWED_ROOTS = ["flipbook", "assets", "media", "out", "transcript.json"];

// GET /api/reel/:id/file/<rel path>[?download=1]
export async function GET(req: Request, { params }: { params: Promise<{ id: string; path: string[] }> }) {
  const { id, path: parts } = await params;
  if (!validId(id) || !parts?.length || !ALLOWED_ROOTS.includes(parts[0])) {
    return new Response("not found", { status: 404 });
  }
  let file: string;
  try {
    file = jobPath(id, ...parts);
  } catch {
    return new Response("not found", { status: 404 });
  }
  const stat = await fs.stat(file).catch(() => null);
  if (!stat?.isFile()) return new Response("not found", { status: 404 });
  const type = TYPES[path.extname(file).toLowerCase()] ?? "application/octet-stream";
  const headers: Record<string, string> = { "Content-Type": type, "Accept-Ranges": "bytes", "Cache-Control": "no-cache" };
  if (new URL(req.url).searchParams.get("download")) {
    headers["Content-Disposition"] = `attachment; filename="${id}_${path.basename(file)}"`;
  }
  // Byte ranges so the <video> element can seek.
  const range = req.headers.get("range")?.match(/bytes=(\d*)-(\d*)/);
  if (range) {
    const start = range[1] ? Number(range[1]) : 0;
    const end = range[2] ? Math.min(Number(range[2]), stat.size - 1) : stat.size - 1;
    const fh = await fs.open(file, "r");
    const buf = Buffer.alloc(end - start + 1);
    await fh.read(buf, 0, buf.length, start);
    await fh.close();
    return new Response(buf, {
      status: 206,
      headers: { ...headers, "Content-Range": `bytes ${start}-${end}/${stat.size}`, "Content-Length": String(buf.length) },
    });
  }
  return new Response(await fs.readFile(file), { headers: { ...headers, "Content-Length": String(stat.size) } });
}
