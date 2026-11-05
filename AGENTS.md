# AGENTS.md — UGC Studio

Read this first. It holds the operator's vision, the rules for working on this
repo, and where the project stands. Where `PRODUCT.md` or
`ugc-system/CONTEXT.md` disagree with this file, **this file wins**. Those two
describe an older operator console from a previous agent.

The operator is **Kartik**, a solo operator building a portfolio of AI UGC
influencer accounts.

---

## 1. The vision

Build the core foundation for creating UGC content. The goals are new video
ideas, brand collaborations and brand integrations. The way there is growing
Instagram accounts run by **AI UGC creators: male, female and gender-neutral**.

The niches are fashion, travel, dance, comedy and tech. They also include
explicit-content creators, who earn mostly through private subscriptions. Their
brand deals come from adult brands (condoms, sexual wellness) and from betting
or prediction sites (1xBet, 4Rabet, Stake, Polymarket, Kalshi). The operator
can't produce all of this by hand. The system is the assistant.

The system has three core parts. More steps are planned but haven't been
described yet. Ask before inventing them.

### 1.1 Reel → playbook (the most important step)

The operator shares an Instagram reel plus:
- **Context:** why this reel fits the persona.
- **Idea / twist:** what to do differently. Or: recreate the reel's script as-is
  with one of the operator's models, because it's already perfect.

**The operator must not have to paste a transcript.** The system:
1. Downloads the reel to a temp/job folder.
2. Separates the audio and transcribes it.
3. Watches the visuals as a **flipbook**: timestamped keyframes covering the
   hook, every cut and the ending.
4. Sends everything to the **mastermind, Claude Opus 5.5**, together with the
   operator's context and idea.

Opus analyses the hook, how the reel flows, how the creator hooked the viewer,
and how it ends. It then returns **two files**:
- **Reel flow:** how the source reel flows, with every hook, graphic and text
  overlay, cut, sound and the ending, in detail.
- **Generation prompts:** detailed prompts for the operator's new version. Same
  essence, new idea, different topic and surroundings. Other image and video
  models must be able to generate every asset from them.

If the operator uploads assets, the prompts use them by filename. Only missing
assets get a generation prompt.

### 1.2 Daily look: outfit and pose

Pick new poses for the persona to post every day, with fashionable clothes that
fit the persona's identity: Prada, LV, Gucci, Skims, Hermès, Nike, Bonkers
Corner, or thrift-market finds.

The operator dumps clothing PNGs and JPEGs into a folder. The selection is
driven by **MDEP: Mood, Day, Environment, Place**. Places are open-ended, for
example:
- their house
- a nearby fast-food restaurant
- a mall
- a famous vacation spot
- work
- a studio photoshoot
- a ramp walk at a fashion show

Jewelry follows the moment. It can be high-end, or **handmade and gifted by
family or friends**. Example: kids pick up unusually shaped shells and pebbles
on a beach, make jewelry from them, and gift it to the influencer. Footwear must
suit the place.

### 1.3 Expressions

Humans have many expressions, and they shift with mood, day, environment and
place. **What the persona is listening to changes their emotions too.** That
matters a lot for reels.

People also mimic real emotions with **performed** ones. Example: a forced
smile while praising a child's first dish from an internet recipe, so the child
doesn't lose confidence. The system must know **when performed expressions are
right and when they're not**. They're never right near a sponsor; brand-trust
moments must look genuine.

### 1.4 Decisions

Selection decisions should come from a calibrated decision model. The operator
named **JEV** (reinforcement learning for calibrated decisions) or an
open-source alternative. Every pick shows its probability, and the system
learns from the operator's feedback.

---

## 2. How to work on this repo (operator's rules)

1. **No dummy logic.** The operator rejected earlier work because it was
   "dummy, fake with no logic" and "nowhere near" the vision. Every feature must
   do the real thing, and every decision must have reasons behind it. Never pass
   off placeholders or demo data as real output. Label them clearly.
2. **The UI must look premium.** A cheap-looking UI was the other big complaint.
   Use the existing design system (section 4.4) and check pages in a browser at
   desktop and phone widths before calling UI work done.
3. **Budget is tight. Commit after every feature,** then push. Small, working
   commits; never leave a large change uncommitted. Keep Opus spend low in
   development (dry-run mode, cheap effort levels for small calls) and show
   cost estimates in the UI.
4. **Opus 5.5 is the mastermind** for anything that needs judgment or vision.
   Use the latest Claude models; don't silently downgrade.
5. **You have a free hand to re-implement** when something is weak. Prefer
   rebuilding a weak part properly over patching it.
6. **Explain in plain words.** The operator asks "why did that happen?" Lead
   with the outcome, then the cause, without jargon.
7. **Be honest about what wasn't verified.** In particular, anything never run
   against a real API key, or never run on Windows.
8. **Use the available skills** when they apply.
9. **Content safety for adult and betting brands:** imply, never show. No
   nudity, no minors, and include the required disclosures (#ad, 18+, play
   responsibly). This is already written into the Opus prompts; keep it.
10. **Ask before inventing** the planned-but-undescribed pipeline steps.

---

## 3. The operator's machine

- **Windows**, project at
  `C:\Users\Kartik\OneDrive\Desktop\New folder\` — inside **OneDrive**.
- Never call `subprocess` directly; use `ugc_system.core.proc.run`. Without it,
  every ffmpeg call flashes a console window on Windows. A test enforces this.
- Never write files with `Path.write_text` or `os.replace` in pipeline code; use
  `ugc_system.core.fsutil.write_text` / `fsutil.remove`. OneDrive and Defender
  briefly lock changed files, and a plain rename then fails with
  `PermissionError: [WinError 5] Access is denied`.
- Don't write status files in tight loops. Progress is throttled to about 2
  writes per second.
- Suggest moving the project, or at least `ugc-system/data/`, out of OneDrive:
  every reel's video, frames and audio land in `data/jobs/`.
- Use Windows-safe paths and commands in docs. The Python executable may be
  `python`; the UI accepts `PYC` / `PYTHON` env vars.
- Instagram downloads usually need a logged-in session:
  `UGC_COOKIES_FROM_BROWSER=chrome` (or a `UGC_COOKIES_FILE`) in
  `ugc-system/.env`, or the operator uploads the video file instead.

### Keys (`ugc-system/.env`, gitignored — never commit it)
- **Opus:** `ANTHROPIC_API_KEY` (model `claude-opus-5-5`) **or**
  `OPEN_ROUTER_API_KEY` (model `anthropic/claude-opus-5.5`). The operator
  already uses OpenRouter.
- **Transcription:** local `faster-whisper` (free, downloads a model on first
  run), or `GROQ_API_KEY` / `OPENAI_API_KEY`.
- `UGC_MASTERMIND_DRY_RUN=1` builds the full Opus request without calling it
  (no spend).

---

## 4. Architecture and conventions

```
AGENTS.md / CLAUDE.md        this guide (CLAUDE.md just imports it)
ugc-system/
  ugc_system/core/           env.py (.env loader), opus.py (ALL Opus calls), proc.py, fsutil.py
  ugc_system/reel_lab/       1.1  job.py, media.py, transcribe.py, flipbook.py, mastermind.py, pipeline.py
  ugc_system/styling/        1.2-1.4  scene.py, wardrobe.py, outfit.py, direction.py, learning.py, planner.py
  ugc_system/engines/ + orchestrator.py + core/decisions.py + bridge.py   old operator console (/console)
  config/styling/            expressions.yaml, poses.yaml, scenes.yaml  (editable knowledge, no code)
  personas/*.yaml            one file per AI influencer
  wardrobe/                  operator's clothing images + .json tag sidecars (demo fallback: assets/seed/)
  data/                      runtime only, gitignored: jobs/, looks/, learning/, styling/
  tests/                     pytest
  ui/                        Next.js 16 app (React 19, TypeScript)
```

### 4.1 Rules for the code
- **Python is the source of truth.** The UI never duplicates logic. API routes
  call Python CLIs: `python -m ugc_system.reel_lab ...` and
  `python -m ugc_system.styling ...`, which print JSON. Long jobs run detached
  and report through `status.json`, which the UI polls.
- **All LLM calls go through `core/opus.py`** (`complete`, `extract_json`,
  `available`). It handles both providers, adaptive thinking, the effort level,
  cost estimates and the server-side refusal fallback.
- Every key-dependent feature must still run without a key: degrade cleanly and
  say so in the UI.
- Every pipeline stage caches on disk. Retry resumes from the failed stage;
  remix and rewrite reuse earlier analysis instead of re-downloading.
- Knowledge (expressions, poses, places, moods, music) lives in YAML so the
  operator can extend it without code changes.

### 4.2 Reel Lab (1.1) — built
- Stages: download (yt-dlp) → audio (ffmpeg, 16 kHz mono, silence map) →
  transcript → flipbook → Opus.
- Transcript: local whisper, or Groq/OpenAI. Uploads are re-encoded to 16 kHz
  Opus (~0.2 MB/min). Above 24 MB they're split into ~10-minute chunks with
  1.5 s overlap, cut at silences, then merged with timestamps shifted and
  overlap duplicates dropped.
- Flipbook: frames every 0.5 s of the first 3 s, every scene cut, even coverage
  and the last frame (max 48), plus a contact sheet.
- Outputs: `out/reel_flow.md`, `out/generation_prompts.md`,
  `out/blueprint.json`. The Opus output streams live into the UI.
- The mastermind prompt lives in `reel_lab/mastermind.py`.

### 4.3 Daily Look (1.2–1.4) — built
- **Scene:** free text becomes a formality band, ground type, terrain-safe
  footwear, jewelry level, props, lighting, weather by season (persona
  `region`, default India) and contexts (family, kindness, comedy, editorial,
  brand_trust…), plus a target emotion (valence/arousal) blended from mood,
  music and place.
- **Outfit:**
  - Hard rules first: gender expression, formality, weather, footwear, jewelry
    level, rest days (7 for statement pieces, 2 for basics).
  - Then whole outfits are scored on colour harmony (real pixel colours), style
    coherence, one hero piece, persona fit, freshness, gift/thrift story and
    sponsor fit.
  - Items named in the notes are locked in.
  - The UI shows five alternatives, each with P(best).
- **Poses** fit the place and its props and show off the hero piece, picked for
  variety.
- **Expressions:** genuine by default. Performed ones are allowed only in their
  contexts (comedy, kindness, editorial), and never in brand-trust moments.
- **Learning:** a per-persona linear Thompson-sampling learner (the open-source
  alternative to JEV) learns from approve, reject and swap, and tracks Brier
  calibration.
- **Wardrobe:** Opus vision tags images into sidecars. Sidecars marked
  `"tagged_by": "manual"` are never overwritten.

### 4.4 UI design system
- **Style:** dark studio look. All tokens are in `ui/app/lab.css`.
- **Colours:** one lime accent, `#c6f432`, for action and live state; coral for
  errors.
- **Fonts:** Instrument Serif for display, Inter for UI, JetBrains Mono for
  numbers and timestamps.
- **Class prefixes:** `rl-` (shared / Reel Lab), `lk-` (looks), `wd-`
  (wardrobe).
- The old console's `globals.css` loads **only** on `/console`, because its
  class names clash with these.
- **Pages:** `/` Reel Lab, `/looks` Daily Look, `/wardrobe`, `/console`. They
  share `components/lab/TopBar.tsx`.

---

## 5. Commands

Run from `ugc-system/`:
```bash
pip install -r requirements.txt          # plus the ffmpeg binary on PATH
python -m pytest -q tests/               # all tests must pass before committing
python -m ugc_system.reel_lab health     # what's installed / configured
python -m ugc_system.reel_lab new --url <reel> --persona aria --idea "..." --context "..." --run
python -m ugc_system.styling plan --persona aria --place "home" --mood cozy --notes "..."
```

Run from `ugc-system/ui/`:
```bash
npm install
npm run dev                              # http://localhost:3000
npx tsc --noEmit -p .                    # type check
npx next build                           # production build check
```

---

## 6. Git and PR workflow
- Work on the branch the session names. Commit after every feature, then push.
- The operator asks for PRs and **squash-merges** them. Once a branch's PR is
  merged, restart the branch from the latest `main` before new work, so the
  next PR shows only new commits.
- No PR template exists. Write PR descriptions with these sections:
  - what changed and why
  - testing
  - what wasn't verified

---

## 7. Status and open items

**Never run against real keys** (the cloud sandbox had none):
- the Opus mastermind
- Opus wardrobe tagging
- the Opus art director
- Groq/OpenAI transcription
- Instagram download (blocked in the sandbox)

**Never run on Windows itself.** The Windows fixes are covered by tests that
simulate the lock and the no-window flag.

**To do / to decide:**
- Persona files need an `appearance:` line (used in every image prompt) and,
  ideally, a `reference_image`. Optional fields: `region` (`india`,
  `india-north`, `southern`) and `wardrobe_expression: fluid`.
- Replace the demo wardrobe (`assets/seed/` placeholder squares) with real
  images in `ugc-system/wardrobe/`, then run **Tag with Opus**.
- JEV isn't wired into the new stylist, because its API couldn't be verified.
  `core/decisions.py` (old console) has the remote seam if JEV access is
  confirmed.
- Not built yet:
  - image/video generation from the prompts
  - posting and scheduling
  - account management
  - linking Reel Lab output to Daily Look (persona outfit and expressions per
    shot)
- The operator has more pipeline steps in mind that haven't been described
  yet. Ask.
