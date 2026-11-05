import numpy as np
import pytest

from ugc_system.styling import direction, learning, outfit, planner, scene, wardrobe


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(planner, "LOOKS", tmp_path / "looks")
    monkeypatch.setattr(learning, "STATE_DIR", tmp_path / "learning")
    monkeypatch.setattr(wardrobe, "WORN_LOG", tmp_path / "worn.jsonl")
    monkeypatch.setattr(scene, "CACHE", tmp_path / "cache.json")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPEN_ROUTER_API_KEY", raising=False)
    monkeypatch.delenv("UGC_LLM_API_KEY", raising=False)


def test_sand_only_allows_beach_footwear():
    s = scene.interpret({"mood": "excited", "place": "Goa beach vacation"})
    assert set(s.footwear) <= {"sandals", "slides", "barefoot"}
    assert s.terrain == "sand" and "travel" in s.contexts and "street" not in s.settings


def test_child_cooking_is_kindness_but_a_gift_is_not():
    cook = scene.interpret({"mood": "happy", "place": "kitchen", "notes": "my niece made pasta for me, too salty"})
    gift = scene.interpret({"mood": "cozy", "place": "home", "notes": "wearing the shell necklace my niece made"})
    assert "kindness" in cook.contexts
    assert "kindness" not in gift.contexts and "family" in gift.contexts


def test_music_pulls_the_target_emotion():
    calm = scene.interpret({"mood": "happy", "place": "cafe"})
    sad = scene.interpret({"mood": "happy", "place": "cafe", "music": "arijit sad songs"})
    assert sad.target_va[0] < calm.target_va[0]


def test_performed_expressions_follow_context_rules():
    by_id = {e["id"]: e for e in direction.expressions()}
    assert direction.expression_allowed(by_id["deadpan"], {"comedy"})[0]
    assert not direction.expression_allowed(by_id["deadpan"], {"travel"})[0]
    assert direction.expression_allowed(by_id["encouraging_smile"], {"kindness", "family"})[0]
    assert not direction.expression_allowed(by_id["encouraging_smile"], {"kindness", "brand_trust"})[0]
    assert direction.expression_allowed(by_id["editorial_stare"], {"editorial", "brand_trust"})[0]


def test_color_harmony_penalises_clashes():
    def item(h):
        return {"category": "top", "colors": [{"name": "x", "hex": h}]}
    neutral, _ = outfit.color_harmony([item("#111111"), item("#f7f7f5")])
    clash, why = outfit.color_harmony([item("#c8102e"), item("#2e8b57"), item("#2f6fd6")])
    assert neutral == 1.0 and clash < 0.6 and "clash" in why or "many" in why


def test_named_items_are_requested():
    items = wardrobe.load()
    hits = outfit.requested_items(items, "wearing the shell necklace my niece made")
    assert [h["id"] for h in hits] == ["handmade_shell_necklace"]


def test_learner_moves_toward_rewarded_features():
    L = learning.Learner("t", "outfit", ["a", "b"], [1, 1])
    X = np.array([[1.0, 0.0], [0.0, 1.0]])
    for _ in range(15):
        L.update(X[0], 0.0, 0.5)
        L.update(X[1], 1.0, 0.5)
    d = L.decide(X, explore=False, seed=1)
    assert d["chosen"] == 1 and d["p_best"][1] > 0.95
    assert abs(sum(d["p_best"]) - 1) < 1e-6
    assert L.calibration()["n"] == 30


def test_plan_end_to_end_and_feedback_rotates_wardrobe():
    look = planner.plan("aria", {"mood": "cozy", "place": "home", "environment": "bedroom with a big mirror",
                                 "notes": "wearing the shell necklace my niece made", "date": "2026-11-05"}, shots=3, seed=5)
    pick = look["outfit"]["alternatives"][look["outfit"]["chosen"]]
    assert "handmade_shell_necklace" in [i["id"] for i in pick["items"]]
    assert len(look["shots"]) == 3 and all(s["image_prompt"] and s["video_prompt"] for s in look["shots"])
    assert abs(sum(a["p_best"] for a in look["outfit"]["alternatives"]) - 1) < 0.01
    planner.feedback(look["id"], "approve")
    worn = wardrobe.worn_days_ago("aria", "2026-11-06")
    assert all(worn.get(i["id"]) == 1 for i in pick["items"])
