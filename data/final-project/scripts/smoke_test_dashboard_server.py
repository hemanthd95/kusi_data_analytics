#!/usr/bin/env python3
"""Connect to a running Bokeh server and verify the interactive document."""
from __future__ import annotations

import argparse

from bokeh.client import pull_session
from bokeh.models import DataTable, Plot, Select, Tabs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5010/app")
    args = parser.parse_args()

    session = pull_session(url=args.url)
    try:
        document = session.document
        if document.title != "Row Crop Intelligence Dashboard":
            raise SystemExit(f"FAIL: unexpected document title: {document.title}")
        if len(document.roots) != 1:
            raise SystemExit("FAIL: dashboard must have one root layout")

        selects = {model.title: model for model in document.select({"type": Select})}
        required = {"Field ID", "Dominant soil type", "Management decision"}
        if set(selects) != required:
            raise SystemExit(f"FAIL: unexpected Select inventory: {set(selects)}")
        if len(selects["Field ID"].options) != 25:
            raise SystemExit("FAIL: Field ID selector must contain 25 fields")
        if len(selects["Management decision"].options) != 5:
            raise SystemExit("FAIL: management selector must contain five tasks")

        tab_models = list(document.select({"type": Tabs}))
        titles = [panel.title for model in tab_models for panel in model.tabs]
        expected_tabs = [
            "Decision Center", "Crop & Vegetation", "Soil & Conservation",
            "Weather & Climate", "Data & Limitations",
        ]
        if titles != expected_tabs:
            raise SystemExit(f"FAIL: unexpected tab inventory: {titles}")
        if len(list(document.select({"type": Plot}))) < 8:
            raise SystemExit("FAIL: fewer than eight Bokeh figures loaded")
        if len(list(document.select({"type": DataTable}))) < 2:
            raise SystemExit("FAIL: expected decision and provenance tables")
    finally:
        session.close()

    print("PASS: live Bokeh dashboard server smoke test succeeded.")


if __name__ == "__main__":
    main()
