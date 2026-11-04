# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js (user-directed). Engine connection: Python bridge — Next.js API routes call the existing, verified Python engines (`ugc-system/ugc_system/`); one source of truth, no logic duplicated.

## Users

Kartik — a solo operator building a portfolio of AI UGC influencer accounts (male, female, gender-neutral personas). He works daily: feeding in Instagram reels + his own raw ideas, then producing content briefs that drive image/video generation for each influencer's posts.

## Product Purpose

A factory control room for AI UGC content production. Takes a reel transcript + the operator's idea and produces one complete, production-ready Content Brief per influencer per day: reel analysis (hook → flow → ending → verdict), outfit/jewelry/footwear/pose styling from a local asset library, and expression direction. Success = an idea walks in one end and a shoot-ready brief walks out the other, fast enough to run multiple influencer accounts daily.

## Positioning

Three specialized engines wired into one assembly line: the Reel Analyzer dissects why a reel works (hook type, beat flow, ending style, remix-vs-recreate verdict), the Stylist dresses the persona from dumped PNG/JPEG asset folders via MDEP context (Mood/Day/Environment/Place), and the Expression Engine directs genuine vs performed emotions. No single generic "AI content tool" does the full line.

## Operating Context

- Input: Instagram reel transcripts (copied/pasted) or raw text ideas, plus the operator's context note on why a reel fits a persona.
- Asset library: local folders of clothing/jewelry/footwear PNGs and JPEGs with optional JSON sidecars (brand, color, formality).
- Personas: one YAML file per influencer (niche, aesthetic, brand tier, jewelry style, voice tone, banned topics).
- Output: JSON Content Briefs in `data/briefs/`, consumed by downstream image/video generation.
- Engines run offline with heuristic fallbacks; optional `UGC_LLM_API_KEY` enables real AI analysis.

## Capabilities and Constraints

- Reel analysis: hook (type + why it works), beat-by-beat flow with timestamps, ending style, verdict (remix vs recreate), remix ideas.
- Styling: MDEP-driven outfit/jewelry/footwear selection scored against place formality band + persona brand tier; pose suggestions per environment.
- Expressions: 10-expression catalog with genuine/performed flags; performed emotions auto-banned for brand-trust reels; warm-kind forced-smile use case encoded.
- Full brief assembly: hook, script outline, style plan, expression plan, caption, hashtags.
- Constraint: UI is a control room over the Python engines, not a reimplementation.
- Open: image/video generation integration not yet built; scheduling/account management not yet in scope.

## Evidence on Hand

- Working, verified Python engine CLI (`ugc-system/ugc_system/`) with sample reel transcript (`data/transcripts/sample.txt`) and prior verified end-to-end run.
- Example persona (`personas/aria.yaml`).

## Product Principles

1. One idea in, one shoot-ready brief out — the factory never stalls on half-finished inputs.
2. Every output is persona-true: styling and expressions always trace back to the persona's identity and the MDEP context.
3. The operator stays the director: verdicts and remix ideas are proposals; the human locks the call.
4. Offline-first core: heuristic fallbacks keep the line running without API keys.
5. Scale by personas, not by headcount — adding an influencer is a YAML file.

## Accessibility & Inclusion

No product-specific requirement established yet; standard web accessibility applies.
