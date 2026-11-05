"""Wardrobe: every clothing / jewelry / footwear image you dump in `wardrobe/`.

    wardrobe/
      gucci/marmont_bag.png          <- folder names are used as hints (brand, tier, category)
      gucci/marmont_bag.json         <- sidecar with the tags (written by `tag`, editable)
      handmade/shell_necklace.jpg

`scan`  indexes images, extracts real colours from the pixels, and guesses
        tags from file/folder names for anything not yet tagged.
`tag`   sends untagged images to Opus 5.5 in batches; it looks at each one and
        writes the full sidecar (category, brand, tier, colours, formality,
        warmth, style, a prompt-ready description, and a story for gifts).
Sidecars marked "tagged_by": "manual" are never overwritten.
"""
from __future__ import annotations

import colorsys
import json
import re
from datetime import date as Date, timedelta
from pathlib import Path

from PIL import Image

from ..core import fsutil, opus
from ..core.env import ROOT

WARDROBE = ROOT / "wardrobe"
DEMO = ROOT / "assets" / "seed"
WORN_LOG = ROOT / "data" / "styling" / "worn.jsonl"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

CATEGORIES = ["top", "bottom", "dress", "outerwear", "footwear", "jewelry", "bag", "accessory"]
TIERS = ["luxury", "premium", "high_street", "streetwear", "sportswear", "thrift", "handmade", "unknown"]
FOOTWEAR_KINDS = ["sneakers", "heels", "flats", "sandals", "slides", "boots", "loafers", "formal_shoes", "sports"]

BRAND_TIER = {
    "luxury": ["prada", "gucci", "louis vuitton", "lv", "hermes", "hermès", "chanel", "dior", "balenciaga", "ysl",
               "saint laurent", "versace", "fendi", "bottega", "cartier", "tiffany", "rolex", "sabyasachi",
               "manish malhotra", "valentino", "miu miu", "loewe", "burberry", "givenchy", "celine"],
    "premium": ["skims", "coach", "michael kors", "ralph lauren", "tommy", "calvin klein", "aritzia", "cos",
                "massimo dutti", "levi", "levis", "levi's", "fabindia", "anita dongre", "tanishq", "pandora", "swarovski"],
    "high_street": ["zara", "h&m", "hm", "mango", "uniqlo", "forever 21", "westside", "max", "only", "vero moda", "shein"],
    "streetwear": ["bonkers corner", "bonkers", "supreme", "stussy", "off-white", "bewakoof", "souled store",
                   "the souled store", "carhartt", "palace", "bape", "jaywalking", "nofilter"],
    "sportswear": ["nike", "adidas", "puma", "lululemon", "gymshark", "under armour", "asics", "reebok",
                   "new balance", "decathlon", "hrx", "jordan"],
    "thrift": ["thrift", "vintage", "secondhand", "second hand", "sarojini", "colaba", "flea"],
    "handmade": ["handmade", "handcrafted", "gift", "gifted", "diy", "homemade", "shell", "pebble"],
}

# name -> hex for the colour names models and people use
PALETTE = {
    "black": "#111111", "charcoal": "#36454f", "grey": "#8e8e8e", "white": "#f7f7f5", "ivory": "#fffff0",
    "cream": "#f3e9d2", "beige": "#d9c7a7", "camel": "#c19a6b", "tan": "#d2b48c", "brown": "#6b4423",
    "chocolate": "#3f2a1d", "navy": "#1f2a44", "denim": "#4a6b8a", "blue": "#2f6fd6", "sky blue": "#87c3eb",
    "teal": "#1b7f7a", "green": "#2e8b57", "olive": "#6b7a3a", "sage": "#a3b18a", "mint": "#a8e6cf",
    "yellow": "#f2c94c", "mustard": "#d4a017", "orange": "#ef7d31", "rust": "#b7472a", "red": "#c8102e",
    "burgundy": "#6d1a36", "maroon": "#5c1a1b", "pink": "#f4a6c1", "hot pink": "#ff3e9a", "blush": "#f2c4c4",
    "lilac": "#c8a2c8", "purple": "#6a3d9a", "gold": "#d4af37", "silver": "#c0c0c0", "rose gold": "#b76e79",
}


def hex_to_hls(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    return hh * 360, l, s


def nearest_color_name(hexv: str) -> str:
    def dist(a, b):
        a, b = a.lstrip("#"), b.lstrip("#")
        return sum((int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) ** 2 for i in (0, 2, 4))
    return min(PALETTE, key=lambda n: dist(PALETTE[n], hexv))


def dominant_colors(path: Path, k: int = 3) -> list[dict]:
    """Real colours from the pixels; drops the white/transparent product background."""
    img = Image.open(path)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img)
    img = img.convert("RGB").resize((96, 96))
    q = img.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in counts)
    out = []
    for c, idx in counts:
        r, g, b = pal[idx * 3: idx * 3 + 3]
        hexv = f"#{r:02x}{g:02x}{b:02x}"
        _, l, s = hex_to_hls(hexv)
        if l > 0.93 and s < 0.25:  # background
            continue
        if c / total < 0.06:
            continue
        name = nearest_color_name(hexv)
        if not any(o["name"] == name for o in out):
            out.append({"name": name, "hex": hexv, "share": round(c / total, 2)})
        if len(out) == k:
            break
    return out


# ------------------------------------------------------------- heuristics
_CAT_WORDS = [
    ("dress", r"dress|gown|jumpsuit|romper|co-?ord|saree|sari|lehenga|anarkali|kurta set|playsuit"),
    ("outerwear", r"jacket|blazer|coat|trench|puffer|cardigan|shrug|overshirt|bomber|parka|shacket"),
    ("footwear", r"shoe|sneaker|heel|pump|sandal|slide|boot|loafer|flat|mule|kolhapuri|jutti|oxford|trainer|stiletto"),
    ("jewelry", r"necklace|chain|ring|earring|hoop|bracelet|bangle|anklet|pendant|choker|jhumka|nose ?pin|watch|jewel"),
    ("bag", r"bag|tote|clutch|purse|backpack|sling|satchel|pouch"),
    ("bottom", r"jean|denim|trouser|pant|skirt|short|legging|cargo|jogger|palazzo|culotte|sweatpant"),
    ("top", r"top|tee|t-?shirt|shirt|blouse|crop|tank|cami|sweater|hoodie|kurta|sweatshirt|bodysuit|corset|polo|bra"),
    ("accessory", r"sunglass|glasses|hat|cap|beanie|belt|scarf|dupatta|hair ?clip|scrunchie|tie\b"),
]
_FOOTWEAR_KIND = [("heels", r"heel|pump|stiletto|mule"), ("sneakers", r"sneaker|trainer|jordan|dunk|air ?force"),
                  ("sandals", r"sandal|kolhapuri"), ("slides", r"slide|flip|crocs"), ("boots", r"boot"),
                  ("loafers", r"loafer"), ("formal_shoes", r"oxford|derby|brogue|formal"),
                  ("flats", r"flat|ballet|jutti|mojari"), ("sports", r"running|sport|gym|training")]


def tier_for(text: str) -> tuple[str, str]:
    t = text.lower()
    for tier, brands in BRAND_TIER.items():
        for b in brands:
            if re.search(rf"(^|[^a-z]){re.escape(b)}([^a-z]|$)", t):
                return tier, ("" if tier in ("thrift", "handmade") else b.title())
    return "unknown", ""


def guess(rel: str) -> dict:
    """Best guess from the path alone — used until Opus (or you) tags it."""
    text = rel.lower().replace("_", " ").replace("-", " ")
    cat = next((c for c, rx in _CAT_WORDS if re.search(rx, text)), "top")
    tier, brand = tier_for(text)
    item = {"category": cat, "brand": brand or ("handmade" if tier == "handmade" else ""), "tier": tier,
            "name": Path(rel).stem.replace("_", " ").replace("-", " ").strip().title()}
    if cat == "footwear":
        item["subcategory"] = next((k for k, rx in _FOOTWEAR_KIND if re.search(rx, text)), "sneakers")
    fem = re.search(r"dress|skirt|heel|blouse|crop|saree|lehenga|bra|corset|cami|clutch|earring|jhumka", text)
    item["gender_expression"] = "feminine" if fem else "neutral"
    item["formality"] = 8 if re.search(r"blazer|gown|heel|tux|suit|saree|lehenga|statement", text) else (
        2 if re.search(r"hoodie|tee|jogger|slide|legging|sweat|crocs|short", text) else 4)
    item["statement"] = 0.8 if re.search(r"statement|sequin|bold|chunky|neon", text) else 0.3
    item["style_tags"] = [t for t in ("minimal", "streetwear", "vintage", "y2k", "boho", "formal", "sporty",
                                      "ethnic", "handmade", "statement", "cozy", "edgy", "preppy")
                          if t in text] or ["casual"]
    if tier == "handmade":
        item["story"] = "handmade piece — add who made it in the sidecar"
    item["warmth"] = 4 if re.search(r"coat|puffer|sweater|hoodie|boot|wool", text) else 2
    return item


DEFAULTS = {"subcategory": "", "colors": [], "pattern": "solid", "material": "", "occasions": [],
            "seasons": [], "description": "", "story": "", "statement": 0.3, "warmth": 2,
            "formality": 4, "gender_expression": "neutral", "style_tags": []}


def _normalise(d: dict) -> dict:
    out = {**DEFAULTS, **d}
    out["category"] = out.get("category") if out.get("category") in CATEGORIES else "top"
    out["tier"] = out.get("tier") if out.get("tier") in TIERS else tier_for(out.get("brand", ""))[0]
    out["formality"] = int(max(1, min(10, round(float(out["formality"])))))
    out["warmth"] = int(max(1, min(5, round(float(out["warmth"])))))
    out["statement"] = round(max(0.0, min(1.0, float(out["statement"]))), 2)
    for c in out["colors"]:
        if isinstance(c, dict) and not c.get("hex") and c.get("name") in PALETTE:
            c["hex"] = PALETTE[c["name"]]
    out["colors"] = [c if isinstance(c, dict) else {"name": c, "hex": PALETTE.get(c, "#888888")} for c in out["colors"]]
    return out


def _legacy(d: dict) -> dict:
    """Map the old assets/seed sidecar schema onto the new one."""
    cat = {"full-fit": "dress", "accessory": "accessory"}.get(d.get("category"), d.get("category"))
    brand = (d.get("brands") or [""])[0]
    return {"category": cat, "brand": brand, "tier": tier_for(brand)[0],
            "colors": [{"name": c, "hex": PALETTE.get(c, "#888888")} for c in d.get("colors", [])],
            "style_tags": d.get("style_tags", []), "formality": d.get("formality", 4)}


# ------------------------------------------------------------- index
def source_dir() -> tuple[Path, bool]:
    has_real = WARDROBE.exists() and any(p.suffix.lower() in IMAGE_EXTS for p in WARDROBE.rglob("*"))
    return (WARDROBE, False) if has_real else (DEMO, True)


def scan() -> list[dict]:
    root, demo = source_dir()
    items = []
    for img in sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_EXTS):
        rel = img.relative_to(root).as_posix()
        side = img.with_suffix(".json")
        data = json.loads(side.read_text(encoding="utf-8")) if side.exists() else {}
        if data and "tagged_by" not in data:  # old schema
            data = {**guess(rel), **_legacy(data), "tagged_by": "legacy"}
        if not data:
            data = {**guess(rel), "tagged_by": "guess"}
        if not data.get("pixel_colors"):
            data["pixel_colors"] = dominant_colors(img)
        if not data.get("colors"):
            data["colors"] = [{"name": c["name"], "hex": c["hex"]} for c in data["pixel_colors"][:2]]
        data = _normalise(data)
        if data.get("category") == "footwear" and data.get("subcategory") not in FOOTWEAR_KINDS:
            data["subcategory"] = guess(rel).get("subcategory", "sneakers")
        text = json.dumps(data, indent=2, ensure_ascii=False)
        if not side.exists() or side.read_text(encoding="utf-8") != text:  # don't churn OneDrive on every page load
            fsutil.write_text(side, text)
        items.append({**data, "id": re.sub(r"\.[^.]+$", "", rel), "file": rel, "demo": demo,
                      "root": "wardrobe" if not demo else "demo"})
    return items


def load() -> list[dict]:
    return scan()


def image_path(item: dict) -> Path:
    return (DEMO if item.get("demo") else WARDROBE) / item["file"]


# ------------------------------------------------------------- Opus tagging
TAG_SYSTEM = """You are a fashion cataloguer for an AI influencer studio. For each garment/accessory image, return one JSON object. Reply with a JSON array, same order as the images, nothing else.

Keys (use these vocabularies exactly):
- category: top | bottom | dress (incl. jumpsuit, co-ord set, saree, lehenga, kurta set) | outerwear | footwear | jewelry | bag | accessory
- subcategory: specific type. For footwear use one of: sneakers heels flats sandals slides boots loafers formal_shoes sports
- name: short product-style name, e.g. "Black leather Marmont shoulder bag"
- brand: brand if visible or confidently recognisable, else "" (never guess a luxury brand without a visible logo/signature design; the folder hint may name it)
- tier: luxury | premium | high_street | streetwear | sportswear | thrift | handmade | unknown
- colors: [{"name": ..., "hex": "#rrggbb"}] main colours, most dominant first (max 3)
- pattern, material: short words
- formality: 1 (gym/lounge) .. 10 (black tie / bridal)
- warmth: 1 (hot-weather) .. 5 (heavy winter)
- statement: 0..1 how much it grabs attention (plain tee 0.1, sequin blazer 0.9)
- gender_expression: feminine | masculine | neutral
- style_tags: 2-5 of minimal streetwear vintage y2k boho formal sporty ethnic handmade statement cozy edgy preppy romantic glam athleisure classic
- occasions: 2-5 of home street cafe restaurant fastfood mall beach pool nature landmark studio runway office gym nightlife festive airport campus date wedding
- seasons: any of summer monsoon winter spring autumn all
- description: one precise sentence an image model can reproduce: silhouette, fit, length, fabric, colour, details, logo placement
- story: for handmade / gifted / thrifted pieces, a short plausible line for captions if the hint suggests one, else ""
"""


def tag(force: bool = False, batch: int = 6, progress=lambda m: None) -> dict:
    items = scan()
    todo = [i for i in items if force and i.get("tagged_by") != "manual" or i.get("tagged_by") in ("guess", "legacy")]
    if not todo:
        return {"tagged": 0, "cost_usd": 0.0, "remaining": 0}
    cost, done = 0.0, 0
    for start in range(0, len(todo), batch):
        chunk = todo[start:start + batch]
        parts = []
        for n, it in enumerate(chunk, 1):
            parts.append({"type": "text", "text": f"Image {n} - path hint: {it['file']}"})
            parts.append({"type": "image", "path": str(image_path(it))})
        parts.append({"type": "text", "text": f"Return a JSON array of {len(chunk)} objects."})
        progress(f"tagging {start + 1}-{start + len(chunk)} of {len(todo)}")
        res = opus.complete({"system": TAG_SYSTEM, "parts": parts}, max_tokens=8000, effort="low")
        cost += res["est_cost_usd"]
        rows = opus.extract_json(res["text"])
        for it, row in zip(chunk, rows if isinstance(rows, list) else []):
            img = image_path(it)
            data = _normalise({**row, "pixel_colors": it.get("pixel_colors", []), "tagged_by": "opus"})
            fsutil.write_text(img.with_suffix(".json"), json.dumps(data, indent=2, ensure_ascii=False))
            done += 1
    return {"tagged": done, "cost_usd": round(cost, 4), "remaining": len(todo) - done}


# ------------------------------------------------------------- wear history
def worn_days_ago(persona: str, today: str) -> dict[str, int]:
    """item id -> days since this persona last wore it."""
    out: dict[str, int] = {}
    if not WORN_LOG.exists():
        return out
    t = Date.fromisoformat(today)
    for line in WORN_LOG.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("persona") != persona:
            continue
        days = (t - Date.fromisoformat(r["date"])).days
        if days < 0:
            continue
        for key in r.get("items", []) + r.get("poses", []) + r.get("expressions", []):
            out[key] = min(out.get(key, 10_000), days)
    return out


def log_worn(persona: str, day: str, items: list[str], poses: list[str], expressions: list[str], look_id: str) -> None:
    WORN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with WORN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"persona": persona, "date": day, "items": items, "poses": poses,
                            "expressions": expressions, "look": look_id}) + "\n")


def since(days: int) -> str:
    return (Date.today() - timedelta(days=days)).isoformat()
