import { NextResponse } from "next/server";
import { execFile } from "node:child_process";
import path from "node:path";

const ALLOWED = new Set([
  "personas",
  "assets",
  "health",
  "scan",
  "analyze",
  "plan-day",
  "brief",
  "line",
  "outcome",
]);

export async function POST(req: Request) {
  let cmd = "";
  let payload: unknown = {};
  try {
    const body = (await req.json()) as { cmd?: string; payload?: unknown };
    cmd = body.cmd ?? "";
    payload = body.payload ?? {};
  } catch {
    return NextResponse.json({ error: "invalid request body" }, { status: 400 });
  }

  if (!ALLOWED.has(cmd)) {
    return NextResponse.json({ error: `unknown command: ${cmd}` }, { status: 400 });
  }

  // The Next server runs from ugc-system/ui; the bridge lives one level up.
  const bridge = path.join(process.cwd(), "..", "bridge.py");
  const python = process.env.PYC || process.env.PYTHON || "python";

  return new Promise<NextResponse>((resolve) => {
    execFile(
      /* turbopackIgnore: true */ python,
      [bridge, cmd],
      { timeout: 180_000, maxBuffer: 16 * 1024 * 1024, windowsHide: true },
      (err, stdout, stderr) => {
        if (err && !stdout) {
          // Python missing, bridge crash before JSON, etc.
          const hint =
            python === "python"
              ? " (is `python` on PATH? set PYC env var to override)"
              : "";
          resolve(
            NextResponse.json(
              { error: `engine failed${hint}: ${stderr || err.message}` },
              { status: 500 },
            ),
          );
          return;
        }
        try {
          const data = JSON.parse(stdout);
          resolve(NextResponse.json(data));
        } catch {
          resolve(
            NextResponse.json(
              { error: `unparseable engine output: ${stdout.slice(0, 300)}` },
              { status: 500 },
            ),
          );
        }
      },
    ).stdin?.end(JSON.stringify(payload));
  });
}
