"""Core data models shared by every engine.

Every model is a plain dataclass with a to_dict() so briefs can be dumped
as JSON/YAML for downstream tools (image gen, video gen, schedulers).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


class Verdict(str, Enum):
    """What to do with a source reel."""
    REMIX = "remix"      # change it up: new angle, new setting, new take
    RECREATE = "recreate"  # script is perfect — run it with our model


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


# ---------------------------------------------------------------- MDEP

@dataclass
class MDEP:
    """The context quad that drives styling and expressions.

    Mood:      how the influencer feels today (confident, cozy, mischievous…)
    Day:       weekday/weekend, season, weather, occasion
    Environment: the physical surroundings (home, mall, beach, studio…)
    Place:     the specific spot within the environment (food court, ramp,
               kitchen counter…)
    """
    mood: str = "neutral"
    day: str = "casual weekday"
    environment: str = "home"
    place: str = "living room"

    def describe(self) -> str:
        return f"{self.mood} | {self.day} | {self.environment} → {self.place}"


# ---------------------------------------------------------------- Persona

@dataclass
class Persona:
    """One AI influencer account."""
    id: str
    name: str
    gender: Gender
    age_range: str = "22-26"
    niche: str = "lifestyle"          # fashion | travel | comedy | tech | …
    aesthetic: str = "clean minimal"  # used by the stylist
    brand_tier: list[str] = field(default_factory=lambda: ["thrift"])
    jewelry_style: str = "minimal"
    voice_tone: str = "warm, dry humor"
    follower_style: str = "best-friend energy"
    banned_topics: list[str] = field(default_factory=list)
    notes: str = ""

    @staticmethod
    def from_dict(d: dict) -> "Persona":
        d = dict(d)
        if "gender" in d:
            d["gender"] = Gender(d["gender"])
        return Persona(**d)


# ---------------------------------------------------------------- Reel analysis

@dataclass
class Beat:
    """One beat of the reel's flow."""
    order: int
    timestamp: str          # e.g. "0:00-0:03"
    purpose: str            # hook / setup / escalation / payoff / CTA
    what_happens: str
    technique: str          # e.g. "pattern interrupt", "open loop", "stare at camera"


@dataclass
class Hook:
    text_or_action: str
    hook_type: str          # question | bold-claim | pattern-interrupt | POV | controversy | visual
    why_it_works: str
    first_3_seconds: str


@dataclass
class Ending:
    style: str              # CTA | loop | cliffhanger | punchline | call-to-comments
    detail: str
    loop_close: bool


@dataclass
class ReelAnalysis:
    source: str
    hook: Hook
    beats: list[Beat]
    ending: Ending
    verdict: Verdict
    verdict_reason: str
    user_context: str = ""          # why the user feels it's good for this influencer
    remix_ideas: list[str] = field(default_factory=list)
    niche_tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- Styling

@dataclass
class Asset:
    """A clothing/jewelry/footwear image in the library."""
    path: str
    category: str            # top | bottom | full-fit | jewelry | footwear | accessory
    brands: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    style_tags: list[str] = field(default_factory=list)   # streetwear, formal, cozy…
    formality: int = 5       # 1 street … 10 black-tie


@dataclass
class OutfitPlan:
    items: list[Asset]
    jewelry: Optional[Asset]
    footwear: Optional[Asset]
    rationale: str


@dataclass
class PosePlan:
    poses: list[str]
    shot_notes: str


@dataclass
class StylePlan:
    mdep: MDEP
    outfit: OutfitPlan
    pose: PosePlan
    location_notes: str


# ---------------------------------------------------------------- Expressions

@dataclass
class Expression:
    name: str                      # genuine smile, polite smile, awe, smirk…
    genuine: bool                  # False = performed/mimicked on purpose
    when_to_use: str
    micro_details: str             # eyes, mouth, brow, body language


@dataclass
class ExpressionPlan:
    primary: Expression
    secondary: list[Expression]
    avoid: list[str]
    audio_note: str               # what they're listening to / sound trend
    rationale: str


# ---------------------------------------------------------------- Content Brief

@dataclass
class ContentBrief:
    """The final artifact: everything needed to produce one reel/post."""
    persona_id: str
    mdep: MDEP
    mode: Verdict
    hook: str
    script_outline: list[str]
    style: StylePlan
    expressions: ExpressionPlan
    caption_idea: str
    hashtags: list[str]
    decisions: dict = field(default_factory=dict)
    escalations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
