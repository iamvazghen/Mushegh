"""Derive the website's brand images from the canonical sources.

The two supplied marks are opposite in polarity: the wordmark is *white* art on a
transparent ground (it only reads on a dark surface) and the glyph is *black* art on
a transparent ground (it only reads on a light one). The site is dark-only
(`--bg: #06090b`), so:

  * banner.png  is copied through untouched -- it is already white-on-transparent,
    which is exactly what the dark hero needs.
  * logo.png    is recoloured to white with its alpha preserved. Shipping the black
    source as-is would render an invisible mark in the dark sidebar; recolouring by
    alpha rather than by threshold keeps the antialiasing exactly as drawn.
  * og.png      is the banner on an opaque 1200x630 site-coloured card. Social
    scrapers have no reliable answer for transparent images.
  * icon.png    is the glyph on an opaque site-coloured square, so it survives both
    light and dark browser chrome.

Canonical sources live in website/brand/ and are never modified. Run:

    .venv\\Scripts\\python.exe tools\\brand_assets.py

Every derived byte is a pure function of a source file, so this is safe to re-run.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "website" / "brand"
PUBLIC = ROOT / "website" / "public"
APP = ROOT / "website" / "app"

# The site's own background (globals.css --bg). Kept in sync by hand; the build
# does not read CSS, and a stale colour here is visible immediately in the favicon.
SITE_BG = (6, 9, 11, 255)

BANNER_SRC = BRAND / "banner-source.png"
LOGO_SRC = BRAND / "logo-source.png"

# Open Graph's recommended card. 1200x630 is what Twitter/Facebook/LinkedIn crop to.
OG_SIZE = (1200, 630)
OG_BANNER_WIDTH = 960


def fail(msg: str) -> "None":
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _require_sources() -> None:
    missing = [p.name for p in (BANNER_SRC, LOGO_SRC) if not p.exists()]
    if missing:
        fail(
            "missing canonical source(s): "
            + ", ".join(missing)
            + f" -- expected under {BRAND}"
        )


def _whitened(im: Image.Image) -> Image.Image:
    """White art carrying `im`'s original alpha.

    Anti-aliasing lives in the alpha channel (the source is black RGB with a soft
    alpha edge), so replacing the RGB channels leaves the shape exactly as drawn.
    """
    white = Image.new("RGBA", im.size, (255, 255, 255, 0))
    white.putalpha(im.getchannel("A"))
    return white


def _trim(im: Image.Image, pad_frac: float = 0.04) -> Image.Image:
    """Crop to the alpha bounding box plus a small even margin.

    The supplied glyph is a 500x500 canvas whose mark occupies only part of it. Left
    untrimmed it renders at ~60% of whatever box CSS gives it, so the 34px sidebar
    mark reads as a speck. Trimming is done on the *derived* image only -- the
    canonical source in website/brand/ is never touched.
    """
    bbox = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if bbox is None:
        return im
    pad = round(max(im.size) * pad_frac)
    left = max(0, bbox[0] - pad)
    top = max(0, bbox[1] - pad)
    right = min(im.size[0], bbox[2] + pad)
    bottom = min(im.size[1], bbox[3] + pad)
    return im.crop((left, top, right, bottom))


def recolour_to_white(src: Path, dst: Path) -> str:
    """Write `src` to `dst` as white-on-transparent, trimmed to the mark."""
    im = _trim(_whitened(Image.open(src).convert("RGBA")))
    im.save(dst, optimize=True)
    return f"{dst.relative_to(ROOT)}  {im.size[0]}x{im.size[1]}  white-on-transparent"


def copy_through(src: Path, dst: Path) -> str:
    im = Image.open(src).convert("RGBA")
    im.save(dst, optimize=True)
    return f"{dst.relative_to(ROOT)}  {im.size[0]}x{im.size[1]}  as-supplied"


def build_og(src: Path, dst: Path) -> str:
    """Banner centred on an opaque site-coloured 1200x630 card."""
    banner = Image.open(src).convert("RGBA")
    width = OG_BANNER_WIDTH
    height = max(1, round(banner.size[1] * width / banner.size[0]))
    banner = banner.resize((width, height), Image.LANCZOS)
    card = Image.new("RGBA", OG_SIZE, SITE_BG)
    card.alpha_composite(banner, ((OG_SIZE[0] - width) // 2, (OG_SIZE[1] - height) // 2))
    card.convert("RGB").save(dst, optimize=True)
    return f"{dst.relative_to(ROOT)}  {OG_SIZE[0]}x{OG_SIZE[1]}  opaque OG card"


def build_icon(src: Path, dsts: list[Path]) -> list[str]:
    """Glyph on an opaque square -- visible against light *and* dark browser chrome.

    Two traps, both real:

    * The glyph must be recoloured *before* compositing. Compositing the black
      source onto the dark tile nests black-on-near-black and the mark vanishes at
      favicon size -- the exact failure this tile exists to prevent.
    * The mark is roughly 2:1, not square. Scaling it to a square box would stretch
      it, so it is fitted to the box by its long edge and centred.
    """
    glyph = _trim(_whitened(Image.open(src).convert("RGBA")))
    side = 512
    inner = 344
    scale = inner / max(glyph.size)
    glyph = glyph.resize(
        (max(1, round(glyph.size[0] * scale)), max(1, round(glyph.size[1] * scale))),
        Image.LANCZOS,
    )
    tile = Image.new("RGBA", (side, side), SITE_BG)
    tile.alpha_composite(glyph, ((side - glyph.size[0]) // 2, (side - glyph.size[1]) // 2))
    tile = tile.convert("RGB")
    out = []
    for dst in dsts:
        tile.save(dst, optimize=True)
        out.append(f"{dst.relative_to(ROOT)}  {side}x{side}  opaque favicon tile")
    return out


def build_readme_assets(banner_src: Path, logo_src: Path) -> list[str]:
    """README copies, composited on the site background.

    GitHub renders a README on a white page *and* a dark one. A white-on-transparent
    wordmark is invisible on the white one, so both files are baked onto the site
    background and always read. Sizes are the ones the README asks for.
    """
    out = []
    banner = Image.open(banner_src).convert("RGBA")
    w = 1200
    h = round(banner.size[1] * w / banner.size[0])
    card = Image.new("RGBA", (w, h + 56), SITE_BG)
    card.alpha_composite(banner.resize((w, h), Image.LANCZOS), (0, 56))
    dst = ROOT / "assets" / "mushegh-banner.png"
    card.convert("RGB").save(dst, optimize=True)
    out.append(f"{dst.relative_to(ROOT)}  {w}x{h + 56}  README banner on site bg")

    glyph = _trim(_whitened(Image.open(logo_src).convert("RGBA")))
    scale = 320 / max(glyph.size)
    glyph = glyph.resize(
        (round(glyph.size[0] * scale), round(glyph.size[1] * scale)), Image.LANCZOS
    )
    side = 400
    tile = Image.new("RGBA", (side, side), SITE_BG)
    tile.alpha_composite(glyph, ((side - glyph.size[0]) // 2, (side - glyph.size[1]) // 2))
    dst = ROOT / "assets" / "mushegh-logo.png"
    tile.convert("RGB").save(dst, optimize=True)
    out.append(f"{dst.relative_to(ROOT)}  {side}x{side}  README logo on site bg")
    return out


def main() -> int:
    _require_sources()
    PUBLIC.mkdir(parents=True, exist_ok=True)

    written = [
        copy_through(BANNER_SRC, PUBLIC / "banner.png"),
        recolour_to_white(LOGO_SRC, PUBLIC / "logo.png"),
        build_og(BANNER_SRC, PUBLIC / "og.png"),
        # app/icon.png is the App Router convention; public/icon.png is what the
        # explicit `icons` metadata points at. Same tile, both resolvable.
        *build_icon(LOGO_SRC, [APP / "icon.png", PUBLIC / "icon.png"]),
        *build_readme_assets(BANNER_SRC, LOGO_SRC),
    ]

    print("brand assets derived:")
    for line in written:
        print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())