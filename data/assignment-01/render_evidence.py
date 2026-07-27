#!/usr/bin/env python3
"""Render the actual saved run log as a portable SVG evidence image."""

from html import escape
from pathlib import Path


HERE = Path(__file__).resolve().parent
lines = (HERE / "output" / "skill_run.log").read_text(encoding="utf-8").splitlines()
height = 105 + 28 * len(lines)
text = "\n".join(
    f'<text x="42" y="{88 + index * 28}" class="terminal">{escape(line)}</text>'
    for index, line in enumerate(lines)
)
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">
<rect width="1200" height="{height}" rx="12" fill="#132019"/>
<rect width="1200" height="52" rx="12" fill="#263c2d"/>
<circle cx="28" cy="26" r="7" fill="#ef6b61"/><circle cx="52" cy="26" r="7" fill="#f4bf4f"/><circle cx="76" cy="26" r="7" fill="#64c867"/>
<text x="600" y="33" text-anchor="middle" fill="#e7f1e9" font-family="sans-serif" font-size="18">Assignment 1 — successful skill run</text>
<style>.terminal {{ fill:#d9eadc; font:18px monospace; }}</style>
{text}
</svg>'''
(HERE / "evidence" / "successful-skill-run.svg").write_text(svg, encoding="utf-8")
print("wrote evidence/successful-skill-run.svg")
