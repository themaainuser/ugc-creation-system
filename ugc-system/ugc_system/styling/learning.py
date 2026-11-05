"""Calibrated decisions that learn from the operator: linear Thompson sampling.

Every choice (outfit, pose set, expression) is described by a feature
vector x in [0, 1]^d ("how well does it fit the formality band", "colour
harmony", "novelty", ...). Each persona has its own Bayesian linear model
of how much each feature predicts the operator's approval:

    reward ~ N(w . x, noise^2),   w ~ N(mu, noise^2 * A^-1)

- Decide: draw w from the posterior and take the best candidate
  (Thompson sampling: explores when unsure, exploits once it has learned).
- P(best): the share of 500 posterior draws in which each candidate wins.
  That is the probability the candidate really is the best one.
- Predicted approval: w_mean . x, compared with the real outcome to keep a
  running Brier score (calibration), shown to the operator.
- Learn: approve = 1, reject = 0, "swap to alternative" = 0 for the pick and
  1 for the chosen alternative; a 1-5 rating or an engagement score can be
  given instead. One closed-form update: A += x x^T, b += r x.

This is the open-source stand-in for a hosted calibrated-decision model
such as JEV: it runs locally with numpy and its state is a small JSON file
per persona and decision type.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..core.env import ROOT
from ..core import fsutil

STATE_DIR = ROOT / "data" / "learning"
PRIOR_STRENGTH = 6.0   # how many observations the hand-set prior is "worth"
NOISE = 0.18


class Learner:
    def __init__(self, persona: str, kind: str, features: list[str], prior: list[float]):
        self.persona, self.kind, self.features = persona, kind, features
        self.path = STATE_DIR / persona / f"{kind}.json"
        d = len(features)
        mu0 = np.array(prior, dtype=float)
        mu0 = mu0 / mu0.sum()  # scores land in [0, 1] before any learning
        self.A = np.eye(d) * PRIOR_STRENGTH
        self.b = PRIOR_STRENGTH * mu0
        self.history: list[dict] = []
        if self.path.exists():
            s = json.loads(self.path.read_text())
            if s.get("features") == features:  # feature set changed -> start over
                self.A, self.b = np.array(s["A"]), np.array(s["b"])
                self.history = s.get("history", [])

    # ---- posterior ------------------------------------------------------
    @property
    def mean(self) -> np.ndarray:
        return np.linalg.solve(self.A, self.b)

    def draws(self, n: int, rng: np.random.Generator) -> np.ndarray:
        cov = NOISE ** 2 * np.linalg.inv(self.A)
        return rng.multivariate_normal(self.mean, cov, size=n, method="cholesky")

    def decide(self, X: np.ndarray, *, explore: bool = True, seed: int | None = None, n: int = 500) -> dict:
        """X: (candidates, d). Returns chosen index, P(best) per candidate, predicted approval."""
        rng = np.random.default_rng(seed)
        W = self.draws(n, rng)
        wins = np.bincount(np.argmax(X @ W.T, axis=0), minlength=len(X))
        p_best = wins / n
        pred = np.clip(X @ self.mean, 0, 1)
        chosen = int(np.argmax(X @ W[0])) if explore else int(np.argmax(pred))
        top = np.sort(p_best)[::-1]
        return {"chosen": chosen, "p_best": [round(float(p), 3) for p in p_best],
                "predicted_approval": [round(float(p), 3) for p in pred],
                "margin": round(float(top[0] - (top[1] if len(top) > 1 else 0)), 3)}

    def explain(self, x: np.ndarray) -> list[dict]:
        """Per-feature contribution to the score, biggest first."""
        m = self.mean
        rows = [{"feature": f, "value": round(float(v), 3), "weight": round(float(w), 3),
                 "contribution": round(float(v * w), 3)} for f, v, w in zip(self.features, x, m)]
        return sorted(rows, key=lambda r: -r["contribution"])

    # ---- learning ---------------------------------------------------------
    def update(self, x: list[float] | np.ndarray, reward: float, predicted: float | None = None, ref: str = "") -> None:
        x = np.asarray(x, dtype=float)
        self.A += np.outer(x, x)
        self.b += reward * x
        if predicted is not None:
            self.history.append({"pred": round(float(predicted), 3), "reward": round(float(reward), 3), "ref": ref})
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fsutil.write_text(self.path, json.dumps({"features": self.features, "A": self.A.tolist(),
                                                 "b": self.b.tolist(), "history": self.history[-500:]}))

    def calibration(self) -> dict:
        h = self.history
        if not h:
            return {"n": 0, "brier": None, "note": "no feedback yet - probabilities are the starting prior"}
        brier = sum((r["pred"] - r["reward"]) ** 2 for r in h) / len(h)
        approve = sum(r["reward"] >= 0.5 for r in h) / len(h)
        return {"n": len(h), "brier": round(brier, 3), "approval_rate": round(approve, 2),
                "avg_predicted": round(sum(r["pred"] for r in h) / len(h), 2)}


def reward_from(verdict: str, rating: int | None = None, engagement: float | None = None,
                baseline: float | None = None) -> float:
    """Map operator feedback to a 0..1 reward."""
    if engagement is not None and baseline:
        ratio = engagement / baseline  # 1.0 = this persona's usual engagement rate
        return float(max(0.0, min(1.0, 0.5 * ratio)))
    if rating is not None:
        return (max(1, min(5, rating)) - 1) / 4
    return {"approve": 1.0, "posted": 1.0, "swap": 0.0, "reject": 0.0}.get(verdict, 0.5)
