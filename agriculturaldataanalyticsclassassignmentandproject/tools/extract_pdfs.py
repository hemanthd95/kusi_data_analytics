#!/usr/bin/env python3
"""Extract text from the assignment PDFs without third-party dependencies.

The PDFs supplied with this project are Skia-generated files with FlateDecode
content streams and embedded ToUnicode character maps.  This small extractor is
deliberately scoped to that format; use Poppler's ``pdftotext`` when available.
"""

from __future__ import annotations

import argparse
import re
import zlib
from pathlib import Path


OBJECT_RE = re.compile(rb"(?m)^(\d+)\s+0\s+obj\b(.*?)^endobj\b", re.DOTALL)
HEX_RE = re.compile(rb"<([0-9A-Fa-f]+)>")


def objects(data: bytes) -> dict[int, bytes]:
    return {int(match[1]): match[2] for match in OBJECT_RE.finditer(data)}


def stream(body: bytes) -> bytes | None:
    # Images and embedded colour profiles can be several megabytes and never
    # contain PDF text operators. Skipping them also avoids treating JPEG bytes
    # as Flate data when a filter array is present.
    header = body.split(b"stream", 1)[0]
    if re.search(rb"/Subtype\s*/Image", header) or b"/N 3" in header and b"/Alternate" in header:
        return None
    match = re.search(rb"stream\r?\n(.*?)\r?\nendstream", body, re.DOTALL)
    if not match:
        return None
    payload = match[1]
    if b"/FlateDecode" in body[: match.start()]:
        try:
            return zlib.decompress(payload)
        except zlib.error:
            return None
    return payload


def unicode_map(cmap: bytes) -> dict[int, str]:
    result: dict[int, str] = {}
    for block in re.findall(rb"beginbfchar(.*?)endbfchar", cmap, re.DOTALL):
        for source, target in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            result[int(source, 16)] = bytes.fromhex(target.decode()).decode("utf-16-be")
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", cmap, re.DOTALL):
        for start, end, target in re.findall(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block
        ):
            first, last, base = int(start, 16), int(end, 16), int(target, 16)
            for offset, code in enumerate(range(first, last + 1)):
                result[code] = chr(base + offset)
    return result


def decode_hex(value: bytes, mapping: dict[int, str]) -> str:
    raw = bytes.fromhex(value.decode())
    width = 2 if len(raw) % 2 == 0 else 1
    return "".join(
        mapping.get(int.from_bytes(raw[index : index + width], "big"), "�")
        for index in range(0, len(raw), width)
    )


def extract(pdf: Path) -> str:
    objs = objects(pdf.read_bytes())
    cmaps: dict[int, dict[int, str]] = {}
    for number, body in objs.items():
        decoded = stream(body)
        if decoded and b"begincmap" in decoded:
            cmaps[number] = unicode_map(decoded)

    fonts: dict[int, dict[int, str]] = {}
    for number, body in objs.items():
        match = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", body)
        if match and int(match[1]) in cmaps:
            fonts[number] = cmaps[int(match[1])]

    aliases: dict[str, dict[int, str]] = {}
    for body in objs.values():
        for alias, reference in re.findall(rb"/(F\d+)\s+(\d+)\s+0\s+R", body):
            if int(reference) in fonts:
                aliases[alias.decode()] = fonts[int(reference)]

    output: list[str] = []
    for _, body in sorted(objs.items()):
        decoded = stream(body)
        if not decoded or b"BT" not in decoded:
            continue
        for text_block in re.findall(rb"BT(.*?)ET", decoded, re.DOTALL):
            current: dict[int, str] = {}
            fragments: list[str] = []
            token_re = re.compile(rb"/(F\d+)\s+[\d.]+\s+Tf|<([0-9A-Fa-f]+)>\s*Tj|\[(.*?)\]\s*TJ", re.DOTALL)
            for token in token_re.finditer(text_block):
                if token[1]:
                    current = aliases.get(token[1].decode(), {})
                elif token[2] and current:
                    fragments.append(decode_hex(token[2], current))
                elif token[3] and current:
                    fragments.extend(decode_hex(value, current) for value in HEX_RE.findall(token[3]))
            line = "".join(fragments).replace("\u200b", "").strip()
            if line:
                output.append(line)
    return "\n".join(output) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(extract(args.input), encoding="utf-8")


if __name__ == "__main__":
    main()
