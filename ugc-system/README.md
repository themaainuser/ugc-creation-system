# UGC Factory — Operator Console

A control room for running AI UGC influencer accounts. Three Python engines
(Reel Analyzer, Stylist, Expression) plus one orchestrator produce a
shoot-ready **Content Brief** per line; a Next.js console operates them —
intake → analyze → brief → re-dress → dispatch — with every sub-choice
routed through a calibrated decision that shows its probabilities, its gate
(automate / escalate), and its rationale.

**Design rule: the Python engines are the single source of truth.** The UI is
a control room, not a second brain: it stores engine output verbatim, filters
it by operator locks at read time, and never re-words a number, a gate, or an
escalation line.

Quality gate: reviewed by a three-delegate council over five rounds,
ending **10/10, 10/10, 10/10** (GLM, DeepSeek, Mimo — see
[Council review](#council-review)).

---

## Table of contents

1. [Architecture](#architecture)
2. [Quick start (step by step)](#quick-start-step-by-step)
3. [Environment variables (.env)](#environment-variables-env)
4. [Models: Jev, the LLM, and the test baseline](#models-jev-the-llm-and-the-test-baseline)
5. [Using the operator console](#using-the-operator-console)
6. [Bridge commands (JSON API)](#bridge-commands-json-api)
7. [CLI reference](#cli-reference)
8. [Asset library](#asset-library)
9. [Personas](#personas)
10. [Calibration & outcomes](#calibration--outcomes)
11. [Tests & verification](#tests--verification)
12. [Troubleshooting](#troubleshooting)
13. [Language rules (glossary & anti-terms)](#language-rules-glossary--anti-terms)
14. [Layout](#layout)
15. [Council review](#council-review)

---

## Architecture

```
transcript + context + idea + MDEP
  → Reel Analyzer   hook typing, beat ladder, ending, verdict decision
  → Stylist         MDEP-driven outfit scoring, calibrated top pick
  → Expression      12-catalog expressions, genuine/performed rules
  → Orchestrator    ContentBrief {decisions, escalations}
  → UI Dispatch     ticket + SAVE → Brier outcome log
```

- `ugc_system/core/decisions.py` — the Jev seam:
  `decide(verb, options, scorer) -> Decision`. Every call returns the full
  distribution, P(chosen), gate (automate/escalate), rationale, and a Brier
  estimate. Remote first (OpenRouter Decisions API), local Platt scaler as
  fallback — never a bare label.
- `ugc_system/core/models.py` — dataclasses shared by the engines
  (`ReelAnalysis.from_dict` rebuilds the UI's analysis echo).
- `ugc_system/engines/reel_analyzer.py` — sentence-split, 150 wpm timing,
  hook/ending pattern rules, structure scoring, guardrailed verdict;
  LLM-typed when configured, deterministic heuristic otherwise.
- `ugc_system/engines/stylist.py` — formality bands per place
  (1 street … 10 black-tie), 6-signal weighted scoring (weights in
  `config/settings.yaml`), cooldown rotation of worn assets.
- `ugc_system/engines/expressions.py` — mood map + hook boost +
  brand-trust / children / recreate hard rules; primary via calibrated
  decision.
- `ugc_system/orchestrator.py` — assembles the brief; **owns escalation
  wording** (`escalation_list`) and logs worn-asset usage for cooldown.
- `bridge.py` — JSON-in/JSON-out bridge the UI calls through
  `/api/engine`; also loads `.env` and maps it onto the engine contract.
- `ui/` — the Next.js operator console (one pure reducer in
  `lib/state.ts`, 36 assertions).

See `docs/DECISIONS.md` for the decision model and `CONTEXT.md` for the
domain glossary (use those exact terms).

---

## Quick start (step by step)

### 0. Prerequisites

- Python 3.10+ with `pip`
- Node.js 20.9+ with `npm` (Next 16's minimum)
- An OpenRouter API key (<https://openrouter.ai/settings/keys>)

### 1. Install

```bash
cd ugc-system
pip install -r requirements.txt     # PyYAML
pip install openai pytest           # LLM path + test runner
cd ui && npm install && cd ..       # UI dependencies
```

### 2. Create your `.env`

Copy the example and put your real key in it (the file is gitignored —
never commit it):

```bash
cp .env.example .env
```

Then edit `.env` (full reference in
[Environment variables](#environment-variables-env)):

```ini
OPEN_ROUTER_API_KEY=sk-or-v1-your-key-here
OPEN_ROUTER_MODEL=typesafe/jev-1.14
OPEN_ROUTER_JEV_BASE_URL=https://openrouter.ai/api/alpha/decisions
OPEN_ROUTER_BASE_URL=https://openrouter.ai/api/v1/chat/completions
UGC_LLM_MODEL=anthropic/claude-opus-5.5
```

You do **not** need to set `JEV_API_KEY` / `UGC_LLM_API_KEY` — the bridge
derives both from the one OpenRouter key.

### 3. Seed data (first run only)

```bash
python -m ugc_system.cli init                  # scaffold folders + aria persona
python assets/seed/make_placeholders.py        # 20 demo wardrobe assets
python -m ugc_system.cli scan-assets assets/seed
```

### 4. Sanity-check the engines

```bash
python bridge.py health
# {"ok":true,"jev":true,"llm":true,
#  "models":{"jev":"typesafe/jev-1.14","llm":"anthropic/claude-opus-5.5"},
#  "assets":20,"personas":5}
```

### 5. Run the tests

```bash
python -m pytest tests -q        # 8 passed
cd ui && npm test && cd ..       # 36 assertions, ALL PASS (back in ugc-system/)
```

### 6. Start the console

```bash
cd ui
npm run build && npm start     # production build
# — or —
npm run dev                    # development with hot reload
```

Open <http://localhost:3000> and go to
[Using the operator console](#using-the-operator-console).

---

## Environment variables (.env)

`.env` lives at `ugc-system/.env`, gitignored by line 11 of the
**repo-root** `.gitignore`. `bridge.py` reads it at startup and maps it
onto the engine's own variable names. **Real environment variables always
win** (the loader only `setdefault`s), so you can override any of this
per-shell.

Lines are `KEY=VALUE`; a `#` at the **start** of a line is a comment, and
` //` starts an inline comment (so URLs keep their `//`). A `#` in the
middle of a value line is **not** stripped by the parser — keep notes on
their own `#` line.

### What to add — the OpenRouter block

| `.env` key | Mapped to | Meaning |
| --- | --- | --- |
| `OPEN_ROUTER_API_KEY` | `JEV_API_KEY` **and** `UGC_LLM_API_KEY` | One key drives both services. |
| `OPEN_ROUTER_JEV_BASE_URL` | `JEV_DECISIONS_URL` | Jev Decisions API endpoint (your `.env` marks it "Jev Specific"). |
| `OPEN_ROUTER_MODEL` | `JEV_MODEL` | Decision model id, e.g. `typesafe/jev-1.14`. |
| `OPEN_ROUTER_BASE_URL` | `UGC_LLM_BASE_URL` | Chat-completions URL; the `/chat/completions` suffix is stripped for the OpenAI SDK. |
| `UGC_LLM_MODEL` | *(stays)* | The LLM used for reel typing / prompt generation. |

### Optional direct engine variables (bypass the mapping if you prefer)

| Variable | Purpose | Default |
| --- | --- | --- |
| `JEV_DECISIONS_URL` | Remote Jev via the Decisions API | unset → local scorer |
| `JEV_BASE_URL` | Legacy TypeSafe System One (`POST {base}/v1/systemone`) | unset |
| `JEV_MODEL` | Decision model id | `typesafe/jev-1.14` (Decisions) / `jev-1.0` (legacy) |
| `JEV_API_KEY` | Bearer token for either Jev surface | from `OPEN_ROUTER_API_KEY` |
| `UGC_LLM_API_KEY` | Enables the LLM path | from `OPEN_ROUTER_API_KEY` |
| `UGC_LLM_BASE_URL` | OpenAI-compatible base URL | from `OPEN_ROUTER_BASE_URL` |
| `UGC_LLM_MODEL` | LLM model id | `stealth/crouton-alpha` via the bridge (test baseline); `gpt-4o-mini` only if you call `core/llm.py` directly without `bridge.py` |
| `PYC` / `PYTHON` | Python executable the UI's API route shells out to | `python` |

### UI-side variables

| Variable | Where | Purpose |
| --- | --- | --- |
| `PYC` or `PYTHON` | `ui` runtime | interpreter used by `/api/engine` (defaults to `python`). |

---

## Models: Jev, the LLM, and the test baseline

### Jev — decisions (TypeSafe, via OpenRouter)

Jev is a **structured decision model**, not a text LLM: you send application
state plus typed questions and get typed answers with calibrated
probabilities back. This project uses the **Decisions API**:

```
POST https://openrouter.ai/api/alpha/decisions
{ "model": "typesafe/jev-1.14",
  "state": { …decision context… },
  "questions": { "decision": { "type": "choice",
      "instructions": "Which verdict is the right call for this reel: …",
      "criteria": { "recreate": "recreate", "remix": "remix" } } } }
→ { "answers": { "decision": { "type": "choice", "choice": "recreate",
      "probabilities": { "recreate": 0.86, "remix": 0.14 }, "confidence": 0.86 } } }
```

- Listed on OpenRouter at ~$0.042/M input tokens, $0 output (billed to
  your account).
- Every decision renders on the **DecisionCard**: full distribution, gate,
  rationale (e.g. `Remote JEV (typesafe/jev-1.14): P(recreate)=0.86 →
  automate (≥0.72 to automate).`), `calibrated: yes` when the remote path
  answered.
- On any error (bad key, network, account setting) it falls back to the
  local Platt scorer — the pipeline never stalls, and `calibrated: no` plus
  a "local fallback" caption tell you honestly which path answered.

### LLM — reel typing & prompt generation (via OpenRouter)

Set `UGC_LLM_MODEL` to one of:

| Model | OpenRouter id | Role | Pricing (in/out per 1M) |
| --- | --- | --- | --- |
| **Claude Opus 5.5** (Anthropic) | `anthropic/claude-opus-5.5` | **Production default in `.env`** — 1M context, structured-output capable | $4 / $20 |
| **GPT-6 Astra** (OpenAI) | `openai/gpt-6-astra` | Production alternative — 1.05M context, flagship reasoning | $10 / $50 |
| **Crouton Alpha** (stealth) | `stealth/crouton-alpha` | **Test baseline only** — free preview, deliberately weak | $0 / $0 |

Why a test baseline: pointing the engine at a weak, free model shows how the
system behaves when the LLM underperforms — heuristic fallback, honest
`calibrated: no`, escalation gates opening, and the console still telling
the truth. Use it to exercise failure paths cheaply; use Opus 5.5 or
GPT-6 Astra for real production lines.

Whatever the model, `reel_analyzer.analyze()` wraps it in
`llm.analyze_text_or_none()` — **any** provider error (404, bad key,
unsupported response, malformed JSON) drops to the deterministic heuristic
with a `[llm] … — heuristic fallback` line on stderr. A dumb or dead model
degrades quality, never correctness.

Switching models is one line in `.env` — keep exactly **one**
`UGC_LLM_MODEL` line active (the bridge re-reads `.env` on every request,
so no restart is needed):

```ini
# Production — Claude Opus 5.5 (the current .env setting)
UGC_LLM_MODEL=anthropic/claude-opus-5.5
# Production alternative:
# UGC_LLM_MODEL=openai/gpt-6-astra
# Test baseline (free, weak):
# UGC_LLM_MODEL=stealth/crouton-alpha
```

The top rail's **LLM** and **JEV** LEDs show which model is configured
(hover for the full id), refreshed every 30 seconds.

---

## Using the operator console

1. **Boot** — `cd ui && npm run build && npm start`, open
   <http://localhost:3000>. The top rail shows persona switcher, engine
   health LEDs (`JEV jev-1.14`, `LLM claude-opus-5.5`, asset/persona
   counts), and today's date.
2. **Pick a persona** — Aria (fashion), Milo (tech), Nova (lifestyle),
   Kai (travel), Zoya (comedy), or your own YAML.
3. **Intake (01)** — paste a reel **transcript** (+ optional context), or
   leave the transcript empty and give an **idea** for an idea-only line.
   Set the **MDEP** shoot day (mood / day / environment / place).
4. **Run line** — the console makes the engine calls in stages so the stage
   rail shows honest progress: `analyze` (hook typing, beats, ending,
   verdict) then `brief`. An *idea-only* run makes a **single** call —
   `brief` straight from Intake, since there is no reel to analyze. A
   **Cancel** button aborts an in-flight run at any point.
   - *Idea-only run:* the Analyzer station shows **Skipped — idea-only
     run** (there is no reel to score), and the ledger says
     **not scored — no reel** instead of pretending anything cleared.
5. **Analyzer (02)** — hook card, beat ladder, ending, and the **Verdict
   stamp** (the effective call). Under it the **JEV DecisionCard** shows
   P for every option, the gate, and the rationale. **Lock the call** to
   freeze it against re-dress, or **override** the verdict to the other
   mode (the brief rebuilds).
6. **Escalations** — right rail's Decision Ledger: every open escalation
   (`verdict: P(remix)=0.55 → escalate`, `wardrobe: empty — …`) with
   **Review** (jump) and **Ack**. Locked verbs drop their line; unlocking
   re-opens the engine's exact wording.
7. **Stylist (03) / Expression (04)** — outfit and expression decisions with
   the same lock authority. Changing MDEP triggers an automatic
   **re-dress** (debounced, abortable, lock-respecting).
8. **Dispatch (05)** — the shoot ticket. **Save brief** writes
   `data/briefs/{persona}_{date}.json` (idempotent per day) and commits the
   cooldown log.
9. **Save outcome** — once the reel is live, record which option actually
   proved correct; the engine scores the decision distribution with Brier
   (lower is better, 0 = exactly right) into
   `data/decisions/outcomes.jsonl`.

Keyboard: the skip link is first, focus rings are visible everywhere, and
the stage rail announces state changes to screen readers.

---

## Bridge commands (JSON API)

`/api/engine` (and `python bridge.py <cmd>` reading JSON on stdin) accepts:

| cmd | payload | returns |
| --- | --- | --- |
| `personas` | `{}` | `{personas:[…]}` |
| `assets` | `{}` | `{assets:[…]}` |
| `health` | `{}` | `{ok, jev, llm, models:{jev,llm}, assets, personas}` |
| `scan` | `{folder}` | `{count, by_category}` |
| `analyze` | `{transcript, context, persona_niche}` | `{analysis, decision}` |
| `brief` / `line` | `{persona, mdep, transcript, context, idea, mode, log, analysis?, verdict_decision?}` | `{brief, analysis}` |
| `plan-day` | `{persona, mdep, hook_text, verdict, hook_type, verdict_decision?}` | `{style, expressions, decisions, escalations}` |
| `save-brief` | `{brief}` | `{path, persona, date, cooldown}` |
| `outcome` | `{verb, chosen, confidence, gate, options, outcome}` | `{brier, record}` |

Notes:

- `analysis` + `verdict_decision` are the **echo**: send the analysis the
  UI already computed and the engine reuses it — one analysis shapes both
  stations, and neither Jev nor the LLM is paid twice.
- `escalations` are always the engine's verbatim lines; the UI only filters
  them by locks.
- Error mapping in `/api/engine`: **400** invalid body or unknown command,
  **500** bridge/Python failure (e.g. `python` not on `PATH`), **502** the
  bridge reported an engine error (e.g. `save-brief` on an empty payload).

Example (works in bash and PowerShell alike):

```bash
echo '{"transcript":"…","context":"…","persona_niche":"fashion"}' | python bridge.py analyze
```

---

## CLI reference

```bash
python -m ugc_system.cli init
python -m ugc_system.cli scan-assets <folder>
python -m ugc_system.cli analyze <transcript.txt> --context "great pacing for Aria"
python -m ugc_system.cli plan-day --persona aria --mood confident --place mall
python -m ugc_system.cli brief <transcript.txt> --persona aria --idea "same script, but thrift store" --mode remix
```

> **Note:** the CLI reads real environment variables only — it does **not**
> load `.env` (that is `bridge.py`'s job). Without exported variables the
> engines still run: Jev uses the local scorer and the LLM path stays off
> (deterministic heuristic). For remote Jev/LLM from the CLI, export the
> variables in your shell first.

---

## Asset library

Drop PNG/JPG into any folder and run `scan-assets`. Optional sidecar
`<name>.json` overrides filename guessing:

```json
{"category":"top","brands":["Prada"],"colors":["black"],
 "style_tags":["formal","statement"],"formality":8}
```

Categories: `top|bottom|full-fit|jewelry|footwear|accessory`. Formality 1..10.
Filename hints: `prada_blazer`, `skims_tee`, `thrift_hoodie`,
`shell_handmade_necklace`, `nike_sneakers`, `heels_formal`. Handmade jewelry
(`handmade/shell/pebble/gift` tags) scores up for personas whose
`jewelry_style` mentions handmade.

---

## Personas

One YAML per influencer in `personas/`. Fields: id, name, gender
(male/female/neutral), age_range, niche, aesthetic, brand_tier (list),
jewelry_style, voice_tone, follower_style, banned_topics, notes. Add a
persona = add a file. Seeded: aria (fashion), milo (tech), nova (lifestyle),
kai (travel), zoya (comedy).

---

## Calibration & outcomes

Each SAVE in the UI logs `{verb, chosen, confidence, gate, outcome, brier}`
to `data/decisions/outcomes.jsonl`. Brier is a proper scoring rule — it
punishes overconfidence. Retune `decision.platt_a/b` and
`automate_threshold` in `config/settings.yaml` as outcomes accumulate.
Worn assets also log to `data/briefs/usage.log` for cooldown rotation
(default 3 days).

---

## Tests & verification

```bash
python -m pytest tests -q        # 8 — decision seam + engines
cd ui && npm test && cd ..       # 36 assertions — reducer: guards, locks, cancel, idea-only
cd ui && npm run build           # clean Next build (typecheck included)
```

What the suites pin down: runId/phase stale-response guards, locks
surviving re-dress, engine escalation wording stored verbatim and filtered
(not re-worded), unlock restoring the exact line, `RUN_CANCEL` staleness,
and idea-only honesty (`analyzeSkipped`). Save-brief idempotence is
verified against the running server (it returns `already-recorded` on a
second save of the same day), not by these unit suites.

---

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `HTTP 404: This model's author is excluded by your account's model author settings` | Your OpenRouter privacy settings exclude that model's author. Enable it at <https://openrouter.ai/settings/privacy>. Until then the engine keeps running on the heuristic fallback (or point `UGC_LLM_MODEL` at the free test baseline). |
| `[llm] … — heuristic fallback` on stderr | Expected degradation: LLM unreachable or misconfigured; analysis continues deterministically. |
| `[jev] decisions api failed … — falling back to local scorer` | Same idea for decisions; `calibrated: no` on the card tells you the local path answered. |
| Health LEDs show `…` | Bridge not reached — check the server is running on :3000 and `python bridge.py health` works from `ugc-system/`. |
| Port 3000 busy | `netstat -ano | findstr :3000`, then `Stop-Process -Id <pid> -Force`. |
| UI build warns about a `package-lock.json` outside the repo | Harmless: Next.js ignores the parent lockfile (set `turbopack.root`/`outputFileTracingRoot` in `next.config.mjs` to silence it). |
| Heuristic output with **no** `[llm]` line on stderr | `openai` package missing (the `LLMUnavailable` path is silent) or `UGC_LLM_API_KEY` unset — `pip install openai` and check the key. With a key but no package the LLM path quietly disables itself. |
| Model changes not picked up | The bridge re-reads `.env` on **every** request — no restart needed for `.env` edits. Only shell-exported variables (`PYC`, `UGC_LLM_MODEL`, …) are inherited when the server starts and need a restart. |

---

## Language rules (glossary & anti-terms)

- **Glossary terms are verbatim** — the exact wording in `CONTEXT.md`
  (Hook, Flow/Beats, Ending, Verdict, MDEP, …) appears unchanged in the UI.
- **Banned in UI copy** (grep across `ui/` must return 0): `engagement`,
  `synergy`, `dummy`, `ML magic`, `smart picks`, `AI magic`.
  (Pre-existing hits inside engine docstrings/domain copy in Python are
  intentionally untouched.)
- Escalation lines are the engine's wording; the UI filters, never rewrites.

---

## Layout

```
config/settings.yaml   decision thresholds, weights, mood map, niche keywords
personas/              one YAML per influencer
assets/seed/           demo wardrobe + generator script
data/transcripts/      input reels
data/briefs/           brief outputs + usage.log
data/decisions/        outcomes.jsonl (calibration log)
docs/DECISIONS.md      decision model + gates + brand-trust rules
CONTEXT.md             domain glossary (use these exact terms)
ugc_system/            engines + orchestrator + cli
bridge.py              JSON bridge + .env loader
tests/                 seam tests (decisions + engines)
ui/                    Next.js operator console (lib/state.ts reducer, 36 assertions)
.env.example           documented environment template (copy to .env)
.env                   your real key — gitignored, never committed
```

---

## Council review

Three delegates (GLM, DeepSeek, Mimo) reviewed every round; Round 4's
must-fixes were fixed in `a5042c6`, and Round 5 verified each one live
(responsive re-measured at 10 viewports, idea-only and cancel paths
exercised, tests re-run).

Rounds: 5

| Delegate | R1 | R2 | R3 | R4 | R5 |
| --- | --- | --- | --- | --- | --- |
| GLM | 5.5 | 8 | 9 | 9.5 | **10** |
| DeepSeek | 5 | 8 | 9 | 9 | **10** |
| Mimo | 5.5 | 8.5 | 9.3 | 9.4 | **10** |
