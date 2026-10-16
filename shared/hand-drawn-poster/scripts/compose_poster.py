#!/usr/bin/env python3
"""Compose two panels without distortion; requires Pillow."""

import argparse
from pathlib import Path

from PIL import Image, ImageOps


def load_image(path):
    with Image.open(path) as source:
        source.seek(0)
        return ImageOps.exif_transpose(source).convert("RGBA")


def prepare_panel(path, size, fit, paper):
    source = load_image(path)
    width, height = source.size
    if fit == "strict" and width * 2 != height * 3:
        raise ValueError(f"{path}: expected a 3:2 panel, got {width}x{height}")
    panel = Image.new("RGB", size, paper)
    if fit == "contain":
        fitted = ImageOps.contain(source, size, Image.Resampling.LANCZOS)
    else:
        fitted = source.resize(size, Image.Resampling.LANCZOS)
    offset = ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2)
    panel.paste(fitted, offset, fitted)
    return panel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo", type=Path, required=True)
    parser.add_argument("--illustration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1536)
    parser.add_argument("--height", type=int, default=2048)
    parser.add_argument("--photo-fit", choices=("strict", "contain"), default="strict")
    parser.add_argument("--paper-color", default="#F2EBDD")
    args = parser.parse_args()
    if args.width <= 0 or args.height <= 0 or args.width * 4 != args.height * 3:
        parser.error("Output must have positive dimensions with an exact 3:4 ratio")
    if args.height % 2:
        parser.error("Output height must be even for equal panels")
    if args.output.suffix.lower() != ".png":
        parser.error("Output filename must end in .png")
    output_path = args.output.resolve()
    if output_path in (args.photo.resolve(), args.illustration.resolve()):
        parser.error("Output must not overwrite an input image")
    size = (args.width, args.height // 2)
    try:
        photo = prepare_panel(args.photo, size, args.photo_fit, args.paper_color)
        illustration = prepare_panel(args.illustration, size, "strict", args.paper_color)
        canvas = Image.new("RGB", (args.width, args.height), args.paper_color)
        canvas.paste(photo, (0, 0))
        canvas.paste(illustration, (0, size[1]))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(args.output, format="PNG")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(f"Saved {args.output}: {args.width}x{args.height}; each panel {size[0]}x{size[1]}")


if __name__ == "__main__":
    main()
