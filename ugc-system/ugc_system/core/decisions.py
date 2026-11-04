"""JEV-style calibrated decision module (RLCD principle).

Design: small interface, deep implementation behind the seam.
Caller asks: `decide(verb, options, features) -> Decision`
Decision always carries: P(each option), chosen, confidence, gate (automate/escalate),
calibration (Platt-scaled), rationale, brier estimate.

- Calibrated: P(true) matches observed accuracy after Platt scaling.
- Proper scoring: Brier taken over full distribution, not just argmax.
- Never a bare label: every choice returns the distribution.
"""
from __future__ import annotations

import json
import math
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import llm

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "settings.yaml"


def _config() -> dict:
    try:
        import yaml
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
    except Exception:
        return {}


@dataclass
class OptionScore:
    name: str
    raw_score: float
    p_calibrated: float
    # which signals pushed this option up/down (for UI explainability)
    signals: list[str] = field(default_factory=list)


@dataclass
class Decision:
    verb: str                      # what question this answers
    options: list[OptionScore]     # full distribution, best first
    chosen: str                    # argmax of calibrated P
    confidence: float              # P(chosen)
    gate: str                      # "automate" | "escalate"
    rationale: str
    brier_estimate: float          # multiclass Brier estimate, matching score_proper (/ n)
    calibrated: bool = True        # whether Platt scaling was applied

    def to_dict(self) -> dict:
        return {
            "verb": self.verb,
            "chosen": self.chosen,
            "confidence": round(self.confidence, 4),
            "gate": self.gate,
            "calibrated": self.calibrated,
            "rationale": self.rationale,
            "brier_estimate": round(self.brier_estimate, 4),
            "options": [
                {"name": o.name, "p": round(o.p_calibrated, 4),
                 "raw": round(o.raw_score, 4), "signals": o.signals}
                for o in self.options
            ],
        }


def _platt(raw: float, a: float = 1.1, b: float = 0.05) -> float:
    """Sigmoid Platt scaling: maps a raw logit/score to calibrated probability."""
    try:
        x = 1.0 / (1.0 + math.exp(-(a * raw + b)))
    except OverflowError:
        x = 1.0 if raw > 0 else 0.0
    return max(1e-4, min(1 - 1e-4, x))


def _softmax(scores: dict[str, float], temp: float = 1.0) -> dict[str, float]:
    if not scores:
        return {}
    vals = {k: v / max(1e-9, temp) for k, v in scores.items()}
    m = max(vals.values())
    exps = {k: math.exp(v - m) for k, v in vals.items()}
    s = sum(exps.values()) or 1.0
    return {k: v / s for k, v in exps.items()}


def _softmax_temp_for_verb(verb: str, cfg_dec: dict | None = None) -> float:
    """Per-verb softmax temperature from ``decision.softmax_temp``.

    Supports a scalar (same temp for every verb) or a ``{verb: temp}`` map
    for per-verb overrides. Defaults to 0.5 if not set in config.
    """
    if cfg_dec is None:
        cfg_dec = _config().get("decision", {}) or {}
    raw = cfg_dec.get("softmax_temp", 0.5)
    if isinstance(raw, dict):
        try:
            return float(raw.get(verb, 0.5))
        except (TypeError, ValueError):
            return 0.5
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.5


def _brier_estimate(confidence: float, n: int) -> float:
    """Multiclass Brier estimate matching :func:`score_proper` (divide by n).

    Uses the same ``/ n`` normalisation as ``score_proper`` so estimates are
    comparable with realised Brier scores logged via ``save_outcome``.
    """
    if n <= 0:
        return 0.0
    return ((1.0 - confidence) ** 2 + (confidence ** 2) * (n - 1) / n) / n


_JEV_BASE = os.environ.get("JEV_BASE_URL", "").rstrip("/")
_JEV_MODEL = os.environ.get("JEV_MODEL", "jev-1.0")


def _jev_remote(verb: str, options: list[str], payload: dict) -> dict[str, float] | None:
    """Try remote JEV (hosted RLCD model) if configured; None → fall back to local scorer.
    Expects POST /v1/systemone {model, verb, options, input} → {probabilities:{name:p}}.
    """
    if not _JEV_BASE:
        return None
    try:
        import urllib.request
        body = json.dumps({
            "model": _JEV_MODEL, "verb": verb, "options": options, "input": payload,
        }).encode()
        req = urllib.request.Request(f"{_JEV_BASE}/v1/systemone", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {os.environ.get('JEV_API_KEY','')}"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        probs = data.get("probabilities") or data.get("probs") or {}
        # normalise
        total = sum(float(v) for v in probs.values()) or 1.0
        return {k: float(v) / total for k, v in probs.items() if k in options}
    except Exception:
        return None


def decide(verb: str, options: dict[str, float] | list[str],
           scorer, context: dict[str, Any] | None = None) -> Decision:
    """Main seam: one call for every calibrated choice in the system.

    `options` is either a list of names (scorer computes raw scores) or a
    pre-scored dict. `scorer(name) -> (raw_score, signals)` for list form.
    """
    context = context or {}
    cfg_dec = _config().get("decision", {}) or {}
    threshold = float(cfg_dec.get("automate_threshold", 0.72))
    a = float(cfg_dec.get("platt_a", 1.1))
    b = float(cfg_dec.get("platt_b", 0.05))
    temp = _softmax_temp_for_verb(verb, cfg_dec)

    if isinstance(options, dict):
        raw_scores = {k: float(v) for k, v in options.items()}
        signals_map = {k: [] for k in raw_scores}
    else:
        raw_scores = {}
        signals_map = {}
        for name in options:
            score, sig = scorer(name)
            raw_scores[name] = float(score)
            signals_map[name] = list(sig)

    # 1. Try remote JEV first (single forward pass, calibrated probabilities)
    remote = _jev_remote(verb, list(raw_scores), {"verb": verb, **context})
    if remote:
        chosen = max(remote, key=remote.get)
        conf = remote[chosen]
        gate = "automate" if conf >= threshold else "escalate"
        return Decision(
            verb=verb,
            options=[OptionScore(n, raw_scores.get(n, 0.0), remote[n], signals_map.get(n, []))
                     for n in sorted(remote, key=remote.get, reverse=True)],
            chosen=chosen, confidence=conf, gate=gate,
            rationale=f"Remote JEV (hosted): P({chosen})={conf:.2f} ≥{threshold} → {gate}.",
            brier_estimate=_brier_estimate(conf, len(remote)),
        )

    # 2. Local heuristic fallback: Platt applied to raw scores (logits) once,
    # then renormalised only if needed to sum to 1.
    # The Platt a/b still come from config defaults — they are not yet fitted
    # to logged outcomes, so this path is reported as calibrated=False until
    # a fit exists (see save_outcome / score_proper for the retuning loop).
    fitted = {k: _platt(float(raw_scores[k]), a, b) for k in raw_scores}
    s = sum(fitted.values()) or 1.0
    # Only renormalise if the per-option Platt outputs don't already sum to ~1.
    if abs(s - 1.0) > 1e-6:
        calibrated = {k: v / s for k, v in fitted.items()}
    else:
        calibrated = fitted
    chosen = max(calibrated, key=calibrated.get)
    conf = calibrated[chosen]
    gate = "automate" if conf >= threshold else "escalate"
    # top signals as rationale
    sigs = signals_map.get(chosen, [])
    rationale = (f"P({chosen})={conf:.2f} → {gate} (≥{threshold} to automate). "
                 + (f"Drove by: {', '.join(sigs[:4])}." if sigs else "No dominant signal — escalate if operator disagrees."))
    brier = _brier_estimate(conf, len(calibrated))
    return Decision(
        verb=verb,
        options=[OptionScore(n, raw_scores[n], calibrated[n], signals_map.get(n, []))
                 for n in sorted(calibrated, key=calibrated.get, reverse=True)],
        chosen=chosen, confidence=conf, gate=gate,
        rationale=rationale, brier_estimate=brier,
        calibrated=False,  # local heuristic path: Platt defaults, not yet fitted to outcomes
    )


def score_proper(decision: Decision, outcome: str) -> float:
    """Brier score of a realised outcome — proper scoring rule.
    Low = well-calibrated. Use to log outcomes and retune Platt a/b.
    """
    probs = {o.name: o.p_calibrated for o in decision.options}
    n = len(probs) or 1
    s = sum((probs[k] - (1.0 if k == outcome else 0.0)) ** 2 for k in probs)
    return s / n if n else 0.0


def save_outcome(log_path: str | Path, decision: Decision, outcome: str) -> dict:
    """Append a Brier-scored record so calibration improves over time."""
    rec = {
        "verb": decision.verb, "chosen": decision.chosen,
        "confidence": decision.confidence, "gate": decision.gate,
        "outcome": outcome, "brier": round(score_proper(decision, outcome), 4),
    }
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec
