#!/usr/bin/env python3
"""Rasterize Decision Engine emblem into Android launcher + splash densities."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets/brand/vision/decision-engine-emblem-square.png"
RES = ROOT / "android/app/src/main/res"
BG = (2, 5, 10, 255)  # #02050A

# Adaptive foreground is typically 108dp; xxxhdpi = 432px. Keep safe-zone padding.
FOREGROUND = {
    "mipmap-mdpi": 108,
    "mipmap-hdpi": 162,
    "mipmap-xhdpi": 216,
    "mipmap-xxhdpi": 324,
    "mipmap-xxxhdpi": 432,
}
LEGACY = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}


def fit_on_canvas(src: Image.Image, size: int, *, pad_ratio: float = 0.12) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), BG)
    inner = max(1, int(size * (1 - pad_ratio * 2)))
    logo = src.convert("RGBA")
    logo.thumbnail((inner, inner), Image.Resampling.LANCZOS)
    x = (size - logo.width) // 2
    y = (size - logo.height) // 2
    canvas.alpha_composite(logo, (x, y))
    return canvas


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing source emblem: {SRC}")
    src = Image.open(SRC)

    for folder, size in FOREGROUND.items():
        out = RES / folder
        out.mkdir(parents=True, exist_ok=True)
        img = fit_on_canvas(src, size, pad_ratio=0.14)
        img.save(out / "ic_launcher_foreground.webp", "WEBP", quality=92)

    for folder, size in LEGACY.items():
        out = RES / folder
        out.mkdir(parents=True, exist_ok=True)
        square = fit_on_canvas(src, size, pad_ratio=0.08)
        square.save(out / "ic_launcher.webp", "WEBP", quality=92)
        # Round mask for round launcher.
        mask = Image.new("L", (size, size), 0)
        from PIL import ImageDraw

        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size - 1, size - 1), fill=255)
        round_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        round_img.paste(square, (0, 0), mask=mask)
        round_img.save(out / "ic_launcher_round.webp", "WEBP", quality=92)

    splash_dirs = [
        "drawable-mdpi",
        "drawable-hdpi",
        "drawable-xhdpi",
        "drawable-xxhdpi",
        "drawable-xxxhdpi",
        "drawable-night-mdpi",
        "drawable-night-hdpi",
        "drawable-night-xhdpi",
        "drawable-night-xxhdpi",
        "drawable-night-xxxhdpi",
    ]
    splash_sizes = {
        "mdpi": 160,
        "hdpi": 240,
        "xhdpi": 320,
        "xxhdpi": 480,
        "xxxhdpi": 640,
    }
    for folder in splash_dirs:
        dens = folder.rsplit("-", 1)[-1]
        size = splash_sizes[dens]
        out = RES / folder
        out.mkdir(parents=True, exist_ok=True)
        img = fit_on_canvas(src, size, pad_ratio=0.1)
        img.save(out / "splashscreen_logo.png", "PNG")

    # Keep Expo asset copies in sync for docs / web.
    app_icon = ROOT / "assets/brand/app-icon.png"
    splash = ROOT / "assets/brand/splash-logo.png"
    fit_on_canvas(src, 1024, pad_ratio=0.08).convert("RGB").save(app_icon, "PNG")
    fit_on_canvas(src, 1024, pad_ratio=0.08).convert("RGB").save(splash, "PNG")
    print(f"Synced Android brand icons from {SRC.name}")


if __name__ == "__main__":
    main()
