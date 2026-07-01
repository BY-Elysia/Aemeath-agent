#!/usr/bin/env python3
"""Build a grounded image-generation prompt for a paper diagram."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DIAGRAM_LABEL = "根据论文内容绘制的解释性示意图"


def fail(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def normalize_line(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    return value


def flatten_json_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {
                "component",
                "components",
                "module",
                "modules",
                "stage",
                "stages",
                "step",
                "steps",
                "flow",
                "flows",
                "arrow",
                "arrows",
                "evidence",
                "quote",
                "caption",
                "claim",
                "section",
                "page",
            }:
                strings.extend(flatten_json_strings(item))
            elif isinstance(item, (dict, list)):
                strings.extend(flatten_json_strings(item))
            elif isinstance(item, str) and len(item.strip()) >= 3:
                strings.append(f"{key}: {item}")
            elif isinstance(item, (int, float)) and key.lower() in {"page", "section"}:
                strings.append(f"{key}: {item}")
    elif isinstance(value, list):
        for item in value:
            strings.extend(flatten_json_strings(item))
    elif isinstance(value, str) and len(value.strip()) >= 3:
        strings.append(value)
    return strings


def extract_markdown_evidence(text: str) -> list[str]:
    evidence: list[str] = []
    in_code_block = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith(("|", "-", "*", ">", "1.", "2.", "3.", "4.", "5.")):
            cleaned = line.strip("#| -*>\t")
            if cleaned and "---" not in cleaned:
                evidence.append(cleaned)
        elif "->" in line or "=>" in line or "Fig." in line or "Sec." in line or "page" in line.lower():
            evidence.append(line)
    return evidence


def read_evidence(path: Path) -> list[str]:
    if not path.exists():
        fail(f"evidence file not found: {path}")
    if not path.is_file():
        fail(f"evidence path is not a file: {path}")

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            fail(f"invalid JSON evidence file: {exc}")
        items = flatten_json_strings(data)
    else:
        items = extract_markdown_evidence(text)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = normalize_line(str(item))
        if len(cleaned) < 3 or cleaned in seen:
            continue
        deduped.append(cleaned)
        seen.add(cleaned)
    return deduped


def build_prompt(diagram_type: str, evidence: list[str], max_items: int) -> str:
    selected = evidence[:max_items]
    evidence_block = "\n".join(f"- {item}" for item in selected)
    type_guidance = {
        "architecture": "Show model modules, inputs, outputs, and explicit connections.",
        "training": "Show training data, model components, objectives, losses, and training stages.",
        "inference": "Show runtime inputs, model or tool steps, decoding/search behavior, and outputs.",
        "data-flow": "Show data sources, filtering, transformation, labeling, retrieval, and final artifacts.",
    }[diagram_type]

    return f"""Create a clean technical {diagram_type} diagram for an LLM paper.

Purpose:
{type_guidance}

Use only the paper-grounded evidence below. Do not add any unsupported modules, arrows, datasets, metrics, objectives, or claims.

Grounded evidence:
{evidence_block}

Diagram requirements:
- White background.
- Clear block diagram style.
- Left-to-right flow unless the evidence clearly implies another layout.
- Readable labels.
- Minimal decoration.
- Use distinct colors for inputs, model components, training or inference steps, and outputs.
- Every box and arrow must be supported by the evidence above.
- If a relation is uncertain, omit the arrow rather than inventing it.
- Add a small footer text exactly: "{DIAGRAM_LABEL}"
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a grounded image-generation prompt for a paper diagram.",
    )
    parser.add_argument("evidence", help="Path to evidence JSON or Markdown")
    parser.add_argument(
        "--diagram-type",
        choices=("architecture", "training", "inference", "data-flow"),
        required=True,
        help="Type of diagram to generate",
    )
    parser.add_argument(
        "--out",
        default="diagram_prompt.md",
        help="Output prompt path (default: diagram_prompt.md)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=40,
        help="Maximum evidence items to include (default: 40)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evidence = read_evidence(Path(args.evidence))
    if not evidence:
        fail("no usable evidence items found")
    if args.max_items < 1:
        fail("--max-items must be at least 1")

    prompt = build_prompt(args.diagram_type, evidence, args.max_items)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(prompt, encoding="utf-8")
    print(f"wrote diagram prompt with {min(len(evidence), args.max_items)} evidence items to {out_path}")


if __name__ == "__main__":
    main()
