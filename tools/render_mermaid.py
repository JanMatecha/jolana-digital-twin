from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs" / "modelica_workflow.mmd"
OUTPUT = ROOT / "jolana_digital_twin" / "presentation" / "static" / "modelica_workflow.svg"


def main() -> int:
    if not INPUT.exists():
        print(f"Mermaid source does not exist: {INPUT}", file=sys.stderr)
        return 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    if shutil.which("mmdc"):
        command = ["mmdc", "-i", str(INPUT), "-o", str(OUTPUT)]
    elif shutil.which("npx"):
        command = [
            "npx",
            "-y",
            "@mermaid-js/mermaid-cli",
            "-i",
            str(INPUT),
            "-o",
            str(OUTPUT),
        ]
    else:
        print(
            "Mermaid CLI is not available. Install it with: npm install -g @mermaid-js/mermaid-cli",
            file=sys.stderr,
        )
        return 1

    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        print(
            "Mermaid render failed. Install Mermaid CLI with: npm install -g @mermaid-js/mermaid-cli",
            file=sys.stderr,
        )
        return result.returncode

    if not OUTPUT.exists() or OUTPUT.stat().st_size == 0:
        print(f"Mermaid render did not create a non-empty SVG: {OUTPUT}", file=sys.stderr)
        return 1

    if "<svg" not in OUTPUT.read_text(encoding="utf-8", errors="ignore"):
        print(f"Generated file does not look like SVG: {OUTPUT}", file=sys.stderr)
        return 1

    print(f"Rendered Mermaid SVG: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
