# Calibrated Decisions (JEV paper principles)

Every non-trivial choice in UGC Factory is a **calibrated decision** — a typed
answer with probabilities, not a bare label. Principle per RLCD research:

- State in, probabilities out. Downstream code automates when P ≥ threshold,
  escalates to the operator otherwise.
- Proper scoring rule (Brier) penalizes overconfidence, so the model learns
  to say "I'm unsure" instead of guessing.
- Platt calibration (sigmoid on raw scores) matches stated P to observed
  accuracy on held-out outcomes.

## The four decisions

| # | Verb | Options | Threshold | Output |
|---|------|---------|-----------|--------|
| 1 | `verdict` | remix / recreate | P ≥ 0.72 → automate | Which script treatment wins; guardrails require hook ≥ 0.80 AND structure ≥ 0.75 for recreate |
| 2 | `outfit` | top-N candidates (per category) | same | Wardrobe pick with signals (formality, place/mood tags, brand tier, aesthetic, handmade, cooldown) |
| 3 | `expression` | 12-expression catalog | same | Primary expression; performed banned for brand-trust → escalate instead of forcing a fake face |
| 4 | `formality` | per-place 1..10 band | deterministic | Hard band filter before scoring (no heels at beach band 1-4; formal only 8-10) |

## Gate: automate vs escalate

- `automate` — P(chosen) ≥ 0.72 → operator can accept without review.
- `escalate` — P < 0.72 → escalate flag on brief; operator decides. Escalations are surfaced in Dispatch with red highlight.
- Every decision carries: `options[{name,p,signals}]`, `confidence`, `gate`, `rationale`, `brier_estimate`, `calibrated:true`.

## Learning loop

1. Operator runs a brief (real P returned).
2. Operator shoots/posts, then logs outcome via UI SAVE or `outcome` bridge command with `o` = actual observed winner.
3. `data/decisions/outcomes.jsonl` appends `{verb, chosen, confidence, gate, outcome, brier}`.
4. Brier score = mean((p − y)²) over the distribution. Well-calibrated → low Brier.
5. Review outcomes weekly; retune Platt `a/b` or thresholds in `config/settings.yaml` (`decision.platt_a/b`, `automate_threshold`).

## Remote JEV (optional)

Set `JEV_BASE_URL` + `JEV_API_KEY` + `JEV_MODEL` → `POST /v1/systemone`
with `{model, verb, options, input}` returning `{probabilities:{name:p}}`.
Local scorer is the fallback; remote and local implement the same Decision shape,
so UI/API are identical either way.

## Brand-trust rules (expression)

Banned performed emotions when any of these appear in persona.banned_topics
or hook text: sponsor, brand-deal, betting (stake/1xbet/4rabet/polymarket/kalshi),
adult-wellness, condom, sex-wellness, discount code. Verdict `recreate` also
implies genuine-only (script is perfect; mimicry would break the take).
Children-present → warm only (no deadpan/smirk/politeness-performed).
