# UGC System — Domain Glossary

Single source of truth for terms. Engines and UI must use these exact words.

**Reel** — Source short-form video transcript. Input is text; visual cues may be pasted as notes.
**Hook** — First 0–3 seconds pattern. Must be typed: question | bold-claim | pattern-interrupt | POV | controversy | visual.
**Flow / Beats** — Ordered structure: hook → setup → escalation → payoff → CTA. Each beat has purpose + technique.
**Ending** — How reel closes: CTA | loop | cliffhanger | punchline | call-to-comments. `loop_close` = last line replays hook.
**Verdict** — `remix` (change something meaningful) or `recreate` (script is perfect, run as-is with our persona). Calibrated decision, not a guess.
**MDEP** — Context quad that drives styling + expressions. Mood (how persona feels) / Day (weekday, season, weather, occasion) / Environment (physical surroundings) / Place (specific spot). Example: Mood=confident, Day=weekend, Env=mall, Place=food court.
**Persona** — One AI influencer account (male/female/neutral). YAML file: niche, aesthetic, brand tier, jewelry style, voice tone, banned topics.
**Asset** — One clothing/jewelry/footwear image in library. PNG/JPEG + optional JSON sidecar. Category: top|bottom|full-fit|jewelry|footwear|accessory.
**Formality 1..10** — 1 = street/casual, 10 = black-tie. Place bands restrict wardrobe.
**Genuine vs Performed** — Genuine = real emotion. Performed = deliberate mimicry (kind forced smile for child praising, polite nod for brand pitch). Performed is banned in brand-trust moments.
**Content Brief** — Final production artifact: hook + script outline + StylePlan + ExpressionPlan + caption + hashtags. One brief per persona per day.
**JEV Decision** — Calibrated probabilistic answer from RLCD-style model. Never a bare label. Always: options with P(each), confidence, rationale, automate/escalate gate.
**Calibrated** — P(correct) matches empirical accuracy. High confidence = automate; low = escalate to operator.
**Proper scoring rule** — Brier / log score that penalizes overconfidence. Used to learn from outcomes.
**Escalate** — Operator must decide; model uncertainty too high to auto-pick.
**Automate** — Model confidence ≥ threshold; operator can accept without review.

**Anti-terms (never use):** engagement, synergy, dummy, ML magic, smart picks, AI magic.

**Relationships:**
- Reel → ReelAnalysis (hook+flow+ending+verdict)
- Persona + MDEP + Assets → StylePlan (outfit+jewelry+footwear+poses)
- Persona + MDEP + verdict → ExpressionPlan (primary/secondary/avoid/audio)
- ReelAnalysis + StylePlan + ExpressionPlan → ContentBrief (via Orchestrator)
- Every verdict / outfit / expression choice → JEV Decision (with calibrated P)
