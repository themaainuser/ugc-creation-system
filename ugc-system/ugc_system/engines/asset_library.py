"""Asset library — index your dumped clothing/jewelry/footwear images.

Drop PNGs/JPEGs into a folder. Optionally add `<image-name>.json` sidecars
with metadata; otherwise filename tokens become style tags.

Sidecar format:
{
  "category": "top",                 # top|bottom|full-fit|jewelry|footwear|accessory
  "brands": ["Prada"],
  "colors": ["black"],
  "style_tags": ["streetwear", "formal"],
  "formality": 7                     # 1 street .. 10 black-tie
}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..core.models import Asset

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

# filename token → style tag normalization
_TOKEN_MAP = {
    "tshirt": "casual", "tee": "casual", "hoodie": "cozy", "blazer": "formal",
    "suit": "formal", "sneakers": "streetwear", "heels": "formal",
    "thrift": "thrift", "vintage": "thrift", "gown": "formal",
}
_BRANDS = ["prada", "lv", "louis vuitton", "gucci", "skims", "hermes",
           "nike", "bonkers corner", "zara", "uniqlo", "adidas"]


def _tokens_from_filename(name: str) -> tuple[list[str], list[str]]:
    words = re.split(r"[_\-\s]+", name.lower())
    brands = [b for b in _BRANDS if any(b in w for w in words)]
    tags = [t for tok, t in _TOKEN_MAP.items() if tok in name.lower()]
    return brands, list(dict.fromkeys(tags))


def _guess_category(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("jewel", "necklace", "ring", "earring", "bracelet")):
        return "jewelry"
    if any(k in n for k in ("shoe", "sneaker", "heel", "boot", "sandal", "footwear")):
        return "footwear"
    if any(k in n for k in ("dress", "gown", "onesie", "jumpsuit", "fullfit", "full_fit")):
        return "full-fit"
    if any(k in n for k in ("pant", "jean", "skirt", "short", "bottom", "trouser")):
        return "bottom"
    if any(k in n for k in ("bag", "hat", "cap", "scarf", "belt", "sunglass")):
        return "accessory"
    return "top"


def scan(root: str | Path) -> list[Asset]:
    root = Path(root)
    assets: list[Asset] = []
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() not in IMAGE_EXTS:
            continue
        sidecar = p.with_suffix(".json")
        meta = {}
        if sidecar.exists():
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
        brands, tags = _tokens_from_filename(p.stem)
        assets.append(Asset(
            path=str(p),
            category=meta.get("category", _guess_category(p.stem)),
            brands=meta.get("brands", brands),
            colors=meta.get("colors", []),
            style_tags=meta.get("style_tags", tags),
            formality=meta.get("formality", 5),
        ))
    return assets


def save_index(assets: list[Asset], out: str | Path) -> None:
    out = Path(out)
    out.write_text(json.dumps([a.__dict__ for a in assets], indent=2),
                   encoding="utf-8")


def load_index(path: str | Path) -> list[Asset]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Asset(**a) for a in data]
