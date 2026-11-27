"""Render one report diagram in colour and open it so you can screenshot it.

Usage:  python tests/team/scripts/show_diagrams.py cfg|pareto|fish1|fish2
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_word_report as b  # noqa: E402

name = sys.argv[1] if len(sys.argv) > 1 else "cfg"
if name not in ("cfg", "pareto", "fish1", "fish2"):
    sys.exit("Choose one of: cfg, pareto, fish1, fish2")
b.make_assets()
if name == "cfg":
    text = (b.DOCS / "03_Static_Analysis_SonarQube_and_CFG.md").read_text(encoding="utf-8")
    body = re.search(r"```mermaid\n(.*?)```", text, re.S).group(1).splitlines()
    b.render_cfg(body, b.SCRATCH / "cfg.png")
out = b.SCRATCH / f"{name}.png"
print("Opening", out)
os.startfile(out)
