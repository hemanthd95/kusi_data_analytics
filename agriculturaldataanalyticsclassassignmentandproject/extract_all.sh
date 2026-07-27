#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEXT="$ROOT/extracted_text"
IMAGES="$ROOT/.generated/extracted_images"
rm -rf "$TEXT" "$IMAGES"
mkdir -p "$TEXT" "$IMAGES"

for pdf in "$ROOT"/*.pdf; do
  name="$(basename "$pdf" .pdf)"
  python3 "$ROOT/tools/extract_pdfs.py" "$pdf" "$TEXT/$name.txt"
  python3 "$ROOT/tools/extract_pdf_images.py" "$pdf" "$IMAGES/$name"
done

find "$IMAGES" -type d -empty -delete
printf '\nExtraction complete: %s text files, %s page images.\n' \
  "$(find "$TEXT" -type f | wc -l)" "$(find "$IMAGES" -type f | wc -l)"
