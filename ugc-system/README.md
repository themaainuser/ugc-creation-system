# UGC System — AI Influencer Content Foundation

Core foundation for running AI UGC influencer accounts. Three real engines +
one orchestrator, all choices routed through calibrated decisions.

## Quick start

```bash
pip install -r requirements.txt          # PyYAML only (openai optional)
python -m ugc_system.cli init            # scaffold folders + aria persona
python assets/seed/make_placeholders.py  # 20 seeded wardrobe assets
python -m ugc_system.cli scan-assets assets/seed
python -m ugc_system.cli analyze data/transcripts/sample.txt --context "great lighting and pacing for Aria"
python -m ugc_system.cli plan-day --persona aria --mood confident --place mall
python -m ugc_system.cli brief data/transcripts/sample.txt --persona aria --idea "same script, but thrift store" --mode remix
```

UI (operator console):

```bash
cd ui && npm install && npm run dev
```

Runs on http://localhost:3000. Open "New folder/ugc-system" as cwd for the bridge paths.

## Architecture

```
transcript + context + idea
  → Reel Analyzer (hook typing, beat ladder, ending, verdict decision)
  → Stylist (MDEP-driven scoring, top-N calibrated pick)
  → Expression Engine (12-catalog, genuine/performed rules)
  → Orchestrator → ContentBrief {decisions, escalations}
  → UI Dispatch (ticket + SAVE outcome → Brier log)
```

- `ugc_system/core/decisions.py` — JEV seam: `decide(verb, options, scorer) -> Decision`.
  Every call returns distribution + P + gate (automate/escalate) + rationale + Brier.
- `ugc_system/core/models.py` — dataclasses shared by engines.
- `ugc_system/engines/reel_analyzer.py` — sentence-split, 150 wpm timing, hook/ending
  pattern rules, structure scoring, guardrailed verdict.
- `ugc_system/engines/stylist.py` — formality bands per place (1 street … 10 black-tie),
  6-signal weighted scoring (weights in `config/settings.yaml`), cooldown rotation.
- `ugc_system/engines/expressions.py` — mood map + hook boost + brand-trust / children /
  recreate hard rules; primary via calibrated decision.
- `ugc_system/orchestrator.py` — assembles the brief; logs wristband usage for cooldown.

See `docs/DECISIONS.md` and `CONTEXT.md` for the full decision model.

## JEV integration (optional, production)

JEV is a hosted decision model trained with RLCD — it returns calibrated
probabilities in one forward pass. By default everything runs **locally** with
the same Decision shape. To use the remote model:

```bash
export JEV_BASE_URL=https://api.typesafe.ai   # your endpoint
export JEV_API_KEY=...
export JEV_MODEL=jev-1.0
```

Bridge will `POST /v1/systemone {model, verb, options, input}` and normalize
`probabilities`. On any error it falls back to the local scorer — never stalls.

## LLM integration (optional)

Set `UGC_LLM_API_KEY` (+ optional `UGC_LLM_BASE_URL`, `UGC_LLM_MODEL`) to
enable LLM-polished analysis. Without it, every engine runs the deterministic
heuristic offline. `openai` package required only when the key is set.

## Asset library

Drop PNG/JPG into any folder and run `scan-assets`. Optional sidecar
`<name>.json` overrides filename guessing:

```json
{"category":"top","brands":["Prada"],"colors":["black"],
 "style_tags":["formal","statement"],"formality":8}
```

Categories: `top|bottom|full-fit|jewelry|footwear|accessory`. Formality 1..10.
Filename hints: `prada_blazer`, `skims_tee`, `thrift_hoodie`, `shell_handmade_necklace`,
`nike_sneakers`, `heels_formal`. Handmade jewelry (`handmade/shell/pebble/gift` tags)
scores up for personas whose `jewelry_style` mentions handmade — e.g. Nova's
shell necklace and niece-gifted pebble ring.

## Personas

One YAML per influencer in `personas/`. Fields: id, name, gender (male/female/neutral),
age_range, niche, aesthetic, brand_tier (list), jewelry_style, voice_tone,
follower_style, banned_topics, notes. Add a persona = add a file. Seeded:
aria (fashion), milo (tech), nova (neutral thrift), kai (travel), zoya (comedy).

## Calibration & outcomes

Each SAVE in the UI logs `{verb, chosen, confidence, gate, outcome, brier}` to
`data/decisions/outcomes.jsonl`. Brier is a proper scoring rule — it punishes
overconfidence. Retune `decision.platt_a/b` and `automate_threshold` in
`config/settings.yaml` as outcomes accumulate. Worn assets also log to
`data/briefs/usage.log` for cooldown rotation (default 3 days).

## Production checklist

- [ ] ≥30 real wardrobe assets scanned (not placeholders)
- [ ] 3+ personas with distinct niches + brand tiers
- [ ] `UGC_LLM_API_KEY` set (or accept heuristic-only mode)
- [ ] `JEV_BASE_URL/KEY` set if hosted model is used (or local fallback)
- [ ] Empty `escalations` on dry-run briefs before shooting
- [ ] `python -m pytest tests -q` green

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
tests/                 seam tests (decisions + engines)
```
