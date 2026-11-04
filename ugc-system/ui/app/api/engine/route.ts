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

const clip = (s: string, n = 800) => (s.length > n ? `${s.slice(0, n)}…` : s);

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
        const errOut = clip(stderr || "");

        if (err && !stdout) {
          // Python missing, bridge crash before JSON, etc.
          const hint =
            python === "python"
              ? " (is `python` on PATH? set PYC env var to override)"
              : "";
          resolve(
            NextResponse.json(
              { error: `engine failed${hint}: ${errOut || err.message}` },
              { status: 500 },
            ),
          );
          return;
        }

        let data: unknown;
        try {
          data = JSON.parse(stdout);
        } catch {
          resolve(
            NextResponse.json(
              {
                error: `unparseable engine output: ${clip(stdout, 300)}${
                  errOut ? ` · stderr: ${errOut}` : ""
                }`,
              },
              { status: 500 },
            ),
          );
          return;
        }

        // The bridge reports failures as {"error": ...} on stdout with exit 0.
        // Forward them as non-200 so the client classifies them as engine errors.
        const bridgeErr = (data as { error?: unknown }).error;
        if (typeof bridgeErr === "string" && bridgeErr) {
          resolve(
            NextResponse.json(
              { error: clip(bridgeErr) + (errOut ? ` · stderr: ${errOut}` : "") },
              { status: 502 },
            ),
          );
          return;
        }

        if (err) {
          // Non-zero exit but parseable stdout — serve it, attach stderr note.
          console.warn(`[engine] ${cmd} exited non-zero: ${errOut || err.message}`);
        }
        resolve(NextResponse.json(data));
      },
    ).stdin?.end(JSON.stringify(payload));
  });
}
