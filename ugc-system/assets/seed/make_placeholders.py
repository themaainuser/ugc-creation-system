"""Generates tiny valid PNG placeholders for the seed wardrobe (stdlib only).

Each placeholder is a 4x4 solid-color PNG. Labels live in sidecar JSONs.
"""
from __future__ import annotations
import json, struct, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# name, category, brands, colors, style_tags, formality
SEED = [
    ("skims_cozy_tee", "top", ["Skims"], ["beige"], ["cozy", "casual", "minimal"], 3),
    ("prada_statement_blazer", "top", ["Prada"], ["black"], ["formal", "statement"], 8),
    ("nike_streetwear_hoodie", "top", ["Nike"], ["red"], ["streetwear", "athletic"], 2),
    ("gucci_statement_top", "top", ["Gucci"], ["green"], ["statement", "formal"], 7),
    ("thrift_distressed_tee", "top", ["thrift"], ["washed"], ["thrift", "casual", "streetwear"], 2),
    ("zara_minimal_blouse", "top", ["Zara"], ["white"], ["minimal", "formal"], 6),
    ("levi_casual_jeans", "bottom", ["Zara"], ["blue"], ["casual", "streetwear"], 3),
    ("hermes_formal_trousers", "bottom", ["Hermes"], ["navy"], ["formal", "minimal"], 8),
    ("thrift_vintage_skirt", "bottom", ["thrift"], ["floral"], ["thrift", "casual"], 4),
    ("lv_resort_dress", "full-fit", ["lv"], ["gold"], ["formal", "statement", "resort"], 9),
    ("bonkers_corner_street_dress", "full-fit", ["Bonkers Corner"], ["black"], ["streetwear", "casual"], 4),
    ("skims_minimal_loungeset", "full-fit", ["Skims"], ["taupe"], ["cozy", "casual", "minimal"], 2),
    ("delicate_gold_necklace", "jewelry", ["Hermes"], ["gold"], ["minimal", "formal"], 6),
    ("handmade_shell_necklace", "jewelry", ["handmade"], ["white"], ["thrift", "handmade", "gift"], 3),
    ("handmade_pebble_ring", "jewelry", ["handmade"], ["grey"], ["handmade", "gift", "thrift"], 2),
    ("statement_silver_chain", "jewelry", ["Nike"], ["silver"], ["statement", "streetwear"], 4),
    ("nike_court_sneakers", "footwear", ["Nike"], ["white"], ["streetwear", "athletic"], 3),
    ("heels_formal_pump", "footwear", ["Prada"], ["nude"], ["formal", "minimal"], 7),
    ("thrift_canvas_sandals", "footwear", ["thrift"], ["tan"], ["resort", "casual", "thrift"], 2),
    ("gucci_lux_heels", "footwear", ["Gucci"], ["black"], ["statement", "formal"], 9),
]

def png_solid(r: int, g: int, b: int) -> bytes:
    # 4x4 RGB PNG, no filtering
    raw = b"".join(b"\x00" + bytes([r, g, b]) * 4 for _ in range(4))
    def chunk(t: bytes, d: bytes) -> bytes:
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")

PALETTE = [(240, 230, 210), (20, 20, 20), (200, 40, 40), (30, 80, 40), (120, 110, 100),
          (250, 250, 250), (60, 80, 160), (10, 10, 60), (180, 140, 160), (200, 160, 40),
          (30, 30, 30), (190, 170, 150), (220, 180, 60), (240, 240, 230), (150, 150, 150), (180, 180, 180),
          (250, 250, 250), (220, 190, 170), (210, 170, 110), (20, 20, 20)]

def main() -> None:
    for i, (name, cat, brands, colors, tags, form) in enumerate(SEED):
        png = ROOT / f"{name}.png"
        r, g, b = PALETTE[i % len(PALETTE)]
        png.write_bytes(png_solid(r, g, b))
        side = ROOT / f"{name}.json"
        side.write_text(json.dumps({"category": cat, "brands": brands, "colors": colors,
                                    "style_tags": tags, "formality": form}, indent=2), encoding="utf-8")
        print(f"seeded {png.name} [{cat} f{form} {','.join(tags)}]")
    print(f"done: {len(SEED)} assets")

if __name__ == "__main__":
    main()
