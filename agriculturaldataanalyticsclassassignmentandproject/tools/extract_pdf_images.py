#!/usr/bin/env python3
"""Export embedded JPEG page images from image-only assignment PDFs."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from extract_pdfs import objects


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for _, body in sorted(objects(args.input.read_bytes()).items()):
        header = body.split(b"stream", 1)[0]
        if not re.search(rb"/Subtype\s*/Image", header) or b"/DCTDecode" not in header:
            continue
        match = re.search(rb"stream\r?\n(.*?)\r?\nendstream", body, re.DOTALL)
        if not match:
            continue
        count += 1
        (args.output_dir / f"page-image-{count:02d}.jpg").write_bytes(match[1])
    print(f"exported {count} JPEG image(s) from {args.input.name}")


if __name__ == "__main__":
    main()
