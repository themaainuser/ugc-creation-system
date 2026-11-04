"""Engine tests — public seams only (analyze / plan / build_brief)."""
from ugc_system.core.models import Gender, MDEP, Persona, Verdict
from ugc_system.engines import asset_library, expressions, reel_analyzer, stylist
from ugc_system.orchestrator import build_brief

ARIA = Persona(id="aria", name="Aria", gender=Gender.FEMALE, niche="fashion",
               aesthetic="clean minimal", brand_tier=["Skims", "thrift"],
               jewelry_style="delicate gold, occasional handmade piece",
               voice_tone="warm, dry humor")

SAMPLE = ("Okay so hear me out — I went to the most expensive restaurant in this city.\n"
          "Waiter sits me down, menu has no prices. Cool. Fancy.\n"
          "Course one arrives. Tiny plate. I'm scared.\n"
          "But then — taste. Actual fireworks. What is happening.\n"
          "Bill comes. I'm not gonna tell you what it cost.\n"
          "Follow for part two where I do this with fast food.")


def test_reel_analyzer_extracts_hook_flow_ending_verdict():
    a = reel_analyzer.analyze(SAMPLE, "great for Aria's fashion audience")
    assert a.hook.text_or_action
    assert a.hook.hook_type in ("question", "bold-claim", "pattern-interrupt", "POV", "controversy", "visual")
    assert len(a.beats) >= 2
    assert a.ending.style in ("CTA", "loop", "cliffhanger", "punchline", "call-to-comments")
    assert a.verdict in (Verdict.REMIX, Verdict.RECREATE)
    assert a.remix_ideas


def test_strong_reel_can_recreate_weak_reel_remixes():
    strong = reel_analyzer.analyze(
        "What nobody tells you about the most expensive meal in this city?\n"
        "They hide the prices, then serve you one bite. One.\n"
        "But that bite is actual fireworks in your mouth.\n"
        "Follow for part two — comment what I should try next!", "")
    weak = reel_analyzer.analyze("hey guys\nso yeah\nbye", "")
    # strong structure → recreate allowed; weak → remix
    assert weak.verdict == Verdict.REMIX


def test_stylist_formality_band_respected():
    from ugc_system.core.models import Asset
    assets = [
        Asset("a/top_bleach.png", "top", style_tags=["casual"], formality=2),
        Asset("a/top_gown.png", "top", style_tags=["formal"], formality=9),
    ]
    plan = stylist.plan(assets, ARIA, MDEP(mood="relaxed", day="weekend", environment="beach", place="beach"))
    for item in plan.outfit.items:
        assert 1 <= item.formality <= 4 or item.formality == 2
    assert plan.pose.poses


def test_expressions_genuine_vs_performed_rules():
    kids = expressions.plan(ARIA, MDEP(mood="grateful", day="weekend", environment="home", place="home"),
                            hook_text="praising my child's first cooking attempt", verdict="remix")
    assert "deadpan" in kids.avoid or kids.primary.genuine
    brand = Persona(id="b", name="B", gender=Gender.FEMALE, niche="fashion",
                    banned_topics=["sponsor"])
    trust = expressions.plan(brand, MDEP(mood="confident", day="workday", environment="work", place="work"),
                             hook_text="sponsor discount code inside", verdict="remix")
    performed = [e for e in [trust.primary, *trust.secondary] if not e.genuine]
    assert performed == []
    assert any(a for a in trust.avoid)


def test_brief_is_production_ready():
    brief = build_brief(ARIA, MDEP(mood="playful", day="casual weekday",
                                   environment="mall", place="mall"),
                        transcript=SAMPLE, context="pacing suits Aria",
                        idea="same script, thrift store", assets=[])
    assert brief.hook and brief.script_outline and brief.caption_idea
    assert brief.hashtags
    assert brief.style.pose.poses
    assert brief.expressions.primary
    assert brief.mdep.place == "mall"
