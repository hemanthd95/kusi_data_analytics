---
name: assignment-setup
description: Verify the agricultural assignment workspace and generate starter evidence.
---

# Assignment Setup Skill

Use this skill for Assignment 1 setup verification.

1. Run `python3 data/assignment-01/run_assignment_setup.py` from the repository root.
2. Confirm the report says `PASS` and identifies all supplied assignment PDFs.
3. Review `data/assignment-01/output/environment.json` and `file_inventory.md`.
4. Regenerate the evidence image with
   `python3 data/assignment-01/render_evidence.py`.

The skill uses only the Python standard library and does not modify source PDFs.
