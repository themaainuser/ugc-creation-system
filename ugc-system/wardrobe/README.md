# Wardrobe

Drop clothing, jewelry, footwear and bag images (PNG / JPEG / WebP) here.
Sub-folders are used as hints, e.g. `gucci/`, `thrift/`, `handmade/gifts/`, `nike/sneakers/`.

Then open **Wardrobe** in the UI (or run `python -m ugc_system.styling scan`).
Each image gets a `.json` sidecar next to it. **Tag with Opus** fills it by looking at the image;
edit any sidecar by hand and set `"tagged_by": "manual"` so it is never overwritten.
For handmade or gifted pieces, put who made it in `story` — the stylist features storied pieces in family / home / travel moments.

While this folder has no images, the stylist uses the demo placeholders in `assets/seed/`.
