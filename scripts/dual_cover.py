#!/usr/bin/env python3
"""Persistent styles and non-stretching dual-cover composition."""
import argparse
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIZES = {"horizontal": (1504, 640), "square": (640, 640), "combined": (2144, 640)}


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def templates():
    values = []
    for path in sorted((ROOT / "templates").glob("*/style.json")):
        data = read_json(path)
        data["directory"] = str(path.parent)
        values.append(data)
    return values


def state_path(args):
    return Path(args.state).expanduser().resolve() if args.state else ROOT / "state" / "last-used.json"


def style_by_id(style_id):
    matches = [entry for entry in templates() if entry["id"] == style_id]
    if not matches:
        raise ValueError("Unknown style: " + style_id)
    return matches[0]


def pillow():
    try:
        from PIL import Image, ImageChops, ImageOps
        return Image, ImageChops, ImageOps
    except ImportError:
        raise ValueError("Pillow unavailable. Use an existing bundled Python with Pillow.")


def image(path):
    Image, _, _ = pillow()
    with Image.open(path) as opened:
        opened.load()
        return opened.convert("RGBA")


def exact(path, kind):
    result = image(path)
    if result.size != SIZES[kind]:
        raise ValueError(f"{kind}: expected {SIZES[kind]}, got {result.size}: {path}")
    return result


def destinations(paths, overwrite):
    for path in paths:
        if path.exists() and not overwrite:
            raise ValueError("Output exists; use a versioned filename or --overwrite: " + str(path))
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)


def command_styles(args):
    path = state_path(args)
    emit({"templates": templates(), "last_used": read_json(path) if path.exists() else None,
          "state_file": str(path), "fallback_style": "mono-sci-fi"})


def command_add_style(args):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.id):
        raise ValueError("Style ID must use lowercase letters, digits and hyphens.")
    directory = ROOT / "templates" / args.id
    if directory.exists():
        raise ValueError("Template exists; choose a new ID: " + args.id)
    rules = Path(args.rules_file).read_text(encoding="utf-8").strip()
    if not rules:
        raise ValueError("Style rules cannot be empty.")
    sources = [Path(item).expanduser().resolve() for item in args.reference]
    for source in sources:
        image(source)
    directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".new-style-", dir=directory.parent))
    try:
        refs = []
        for i, source in enumerate(sources, 1):
            dest = staging / f"reference-{i}{source.suffix.lower()}"
            shutil.copy2(source, dest)
            refs.append(dest.name)
        data = {"id": args.id, "name": args.name, "rules": rules, "references": refs}
        atomic_json(staging / "style.json", data)
        staging.rename(directory)
        emit({"added": data, "last_used_updated": False})
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def command_normalize(args):
    Image, _, ImageOps = pillow()
    source = image(args.input)
    target = SIZES[args.kind]
    dest = Path(args.output).expanduser().resolve()
    destinations([dest], args.overwrite)
    background = Image.new("RGB", source.size, args.background)
    background.paste(source, mask=source.getchannel("A"))
    fitted = ImageOps.contain(background, target, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", target, args.background)
    offset = ((target[0] - fitted.width) // 2, (target[1] - fitted.height) // 2)
    canvas.paste(fitted, offset)
    canvas.save(dest, format="PNG")
    emit({"output": str(dest), "size": target, "source_size": source.size,
          "scaled_size": fitted.size, "offset": offset, "stretched": False,
          "note": "Padding may change frame margins; inspect before composition."})


def command_compose(args):
    Image, _, _ = pillow()
    left, right = exact(args.horizontal, "horizontal"), exact(args.square, "square")
    output = Path(args.output).expanduser().resolve()
    previews = [output.with_name(output.stem + "-horizontal.png"), output.with_name(output.stem + "-square.png")]
    report = output.with_name(output.stem + "-geometry.json")
    destinations([output, *previews, report], args.overwrite)
    canvas = Image.new("RGB", SIZES["combined"], args.background)
    canvas.paste(left, (0, 0), left.getchannel("A"))
    canvas.paste(right, (1504, 0), right.getchannel("A"))
    canvas.save(output, format="PNG")
    canvas.crop((0, 0, 1504, 640)).save(previews[0], format="PNG")
    canvas.crop((1504, 0, 2144, 640)).save(previews[1], format="PNG")
    data = {"output": str(output), "size": list(canvas.size), "format": "PNG", "mode": "RGB",
            "horizontal": {"box": [0, 0, 1504, 640], "size": [1504, 640], "preview": str(previews[0])},
            "square": {"box": [1504, 0, 2144, 640], "size": [640, 640], "preview": str(previews[1])},
            "visual_review_required": True}
    atomic_json(report, data)
    emit(data)


def command_inspect(args):
    Image, _, _ = pillow()
    path = Path(args.input).expanduser().resolve()
    with Image.open(path) as source:
        source.load()
        data = {"input": str(path), "size": list(source.size), "format": source.format,
                "mode": source.mode, "bytes": path.stat().st_size}
        if args.ink_bounds:
            mask = source.convert("RGB").convert("L").point(lambda value: 255 if value < 120 else 0)
            box = mask.getbbox()
            data["dark_pixel_bbox"] = box
            data["dark_pixel_margins"] = ([box[0], box[1], source.width - box[2], source.height - box[3]] if box else None)
            data["measurement_note"] = "White-background monochrome only; stars and texture affect bounds."
    emit(data)


def command_remember(args):
    style = style_by_id(args.style)
    left, right = exact(args.horizontal, "horizontal"), exact(args.square, "square")
    result = exact(args.output, "combined")
    Image, ImageChops, _ = pillow()
    expected = Image.new("RGB", SIZES["combined"], args.background)
    expected.paste(left, (0, 0), left.getchannel("A"))
    expected.paste(right, (1504, 0), right.getchannel("A"))
    if ImageChops.difference(expected, result.convert("RGB")).getbbox():
        raise ValueError("Combined output does not match the supplied independent covers.")
    with Image.open(args.output) as opened:
        if opened.format != "PNG":
            raise ValueError("Combined output must be PNG.")
    data = {"schema_version": 1, "style_id": style["id"], "style_name": style["name"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_delivery": {key: str(Path(getattr(args, key)).expanduser().resolve())
                              for key in ("horizontal", "square", "output")}}
    path = state_path(args)
    atomic_json(path, data)
    emit({"saved": str(path), "last_used": data})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", help="Override persistent state file")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("styles").set_defaults(run=command_styles)
    add = sub.add_parser("add-style")
    add.add_argument("--id", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--rules-file", required=True)
    add.add_argument("--reference", action="append", default=[])
    add.set_defaults(run=command_add_style)
    normal = sub.add_parser("normalize")
    normal.add_argument("--input", required=True)
    normal.add_argument("--output", required=True)
    normal.add_argument("--kind", choices=("horizontal", "square"), required=True)
    normal.add_argument("--background", default="white")
    normal.add_argument("--overwrite", action="store_true")
    normal.set_defaults(run=command_normalize)
    compose, remember = sub.add_parser("compose"), sub.add_parser("remember")
    for item in (compose, remember):
        item.add_argument("--horizontal", required=True)
        item.add_argument("--square", required=True)
        item.add_argument("--output", required=True)
        item.add_argument("--background", default="white")
    compose.add_argument("--overwrite", action="store_true")
    compose.set_defaults(run=command_compose)
    remember.add_argument("--style", required=True)
    remember.set_defaults(run=command_remember)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--input", required=True)
    inspect.add_argument("--ink-bounds", action="store_true")
    inspect.set_defaults(run=command_inspect)
    args = parser.parse_args()
    try:
        args.run(args)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, "Error: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
