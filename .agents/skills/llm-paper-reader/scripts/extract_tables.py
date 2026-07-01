#!/usr/bin/env python3
"""Extract cropped table images and metadata from a PDF."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


TABLE_CAPTION_RE = re.compile(
    r"^\s*(?P<label>Table)\s*(?P<number>[A-Za-z0-9][A-Za-z0-9.\-]*)\s*[:.\-]?\s*(?P<caption>.*)$",
    re.IGNORECASE,
)


def fail(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def require_fitz() -> Any:
    try:
        import fitz  # type: ignore
    except ImportError:
        fail(
            "extract_tables.py requires PyMuPDF. Install it with "
            "`python3 -m pip install pymupdf`."
        )
    return fitz


def clean_filename(value: str) -> str:
    value = value.lower().replace(".", "")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "table"


def line_records(page: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for block in page.get_text("dict", sort=True).get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
            if text:
                records.append({"text": text, "bbox": tuple(line.get("bbox", (0, 0, 0, 0)))})
    return records


def page_table_captions(page: Any) -> list[dict[str, Any]]:
    captions: list[dict[str, Any]] = []
    lines = line_records(page)
    index = 0
    while index < len(lines):
        line_text = str(lines[index]["text"]).rstrip()
        match = TABLE_CAPTION_RE.match(line_text)
        if not match:
            index += 1
            continue

        table_id = f"Table {match.group('number')}"
        caption_parts = [match.group("caption").strip()]
        lookahead = index + 1
        while lookahead < len(lines):
            candidate = str(lines[lookahead]["text"]).strip()
            previous_bbox = tuple(lines[lookahead - 1]["bbox"])
            candidate_bbox = tuple(lines[lookahead]["bbox"])
            if float(candidate_bbox[1]) - float(previous_bbox[3]) > 5:
                break
            if not candidate:
                break
            if re.match(r"^\d+(?:\.\d+)*\.\s+", candidate):
                break
            if TABLE_CAPTION_RE.match(candidate) or re.match(
                r"^(Fig(?:ure)?\.?|Algorithm)\s+", candidate, re.IGNORECASE
            ):
                break
            if len(" ".join(caption_parts + [candidate])) > 600:
                break
            caption_parts.append(candidate)
            lookahead += 1

        captions.append(
            {
                "table_id": table_id,
                "caption": " ".join(part for part in caption_parts if part).strip(),
                "bbox": tuple(lines[index]["bbox"]),
            }
        )
        index = max(lookahead, index + 1)
    return captions


def rect_tuple(rect: Any) -> tuple[float, float, float, float]:
    return (float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3]))


def horizontally_aligned(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
    tolerance: float,
) -> bool:
    first_width = max(1.0, first[2] - first[0])
    second_width = max(1.0, second[2] - second[0])
    overlap = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    min_width = min(first_width, second_width)
    return overlap / min_width >= 0.82 or (
        abs(first[0] - second[0]) <= tolerance and abs(first[2] - second[2]) <= tolerance
    )


def merge_table_bboxes(
    bboxes: list[tuple[float, float, float, float]],
    vertical_gap: float,
    x_tolerance: float,
) -> list[tuple[float, float, float, float]]:
    if not bboxes:
        return []

    merged: list[tuple[float, float, float, float]] = []
    for bbox in sorted(bboxes, key=lambda item: (item[1], item[0])):
        if not merged:
            merged.append(bbox)
            continue

        previous = merged[-1]
        gap = bbox[1] - previous[3]
        if 0 <= gap <= vertical_gap and horizontally_aligned(previous, bbox, x_tolerance):
            merged[-1] = (
                min(previous[0], bbox[0]),
                min(previous[1], bbox[1]),
                max(previous[2], bbox[2]),
                max(previous[3], bbox[3]),
            )
        else:
            merged.append(bbox)
    return merged


def overlap_ratio(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    overlap = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    width = max(1.0, min(first[2] - first[0], second[2] - second[0]))
    return overlap / width


def choose_bbox_for_caption(
    caption_bbox: tuple[float, float, float, float],
    bboxes: list[tuple[float, float, float, float]],
    used_indexes: set[int],
) -> tuple[int, tuple[float, float, float, float]] | None:
    scored: list[tuple[float, int, tuple[float, float, float, float]]] = []
    for index, bbox in enumerate(bboxes):
        if index in used_indexes:
            continue

        if bbox[3] <= caption_bbox[1] + 3:
            distance = caption_bbox[1] - bbox[3]
        elif bbox[1] >= caption_bbox[3] - 3:
            distance = bbox[1] - caption_bbox[3]
        else:
            distance = min(abs(caption_bbox[1] - bbox[3]), abs(bbox[1] - caption_bbox[3]))

        x_overlap = overlap_ratio(caption_bbox, bbox)
        if distance > 160 and x_overlap < 0.5:
            continue
        score = distance + (1.0 - x_overlap) * 80
        scored.append((score, index, bbox))

    if not scored:
        return None
    _, index, bbox = min(scored, key=lambda item: item[0])
    return index, bbox


def render_crop(fitz: Any, page: Any, bbox: tuple[float, float, float, float], out_path: Path, zoom: float, padding: float) -> tuple[int, int]:
    page_rect = page.rect
    rect = fitz.Rect(*bbox)
    rect.x0 = max(page_rect.x0, rect.x0 - padding)
    rect.y0 = max(page_rect.y0, rect.y0 - padding)
    rect.x1 = min(page_rect.x1, rect.x1 + padding)
    rect.y1 = min(page_rect.y1, rect.y1 + padding)

    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out_path))
    return pix.width, pix.height


def extract_tables(
    pdf_path: Path,
    out_dir: Path,
    metadata_path: Path,
    zoom: float,
    padding: float,
    merge_gap: float,
    x_tolerance: float,
    include_uncaptioned: bool,
) -> list[dict[str, Any]]:
    fitz = require_fitz()
    records: list[dict[str, Any]] = []

    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc, start=1):
            captions = page_table_captions(page)
            if not captions and not include_uncaptioned:
                continue
            try:
                raw_tables = page.find_tables().tables
            except Exception as exc:
                print(f"warning: table detection failed on page {page_index}: {exc}", file=sys.stderr)
                raw_tables = []

            bboxes = merge_table_bboxes(
                [rect_tuple(table.bbox) for table in raw_tables],
                vertical_gap=merge_gap,
                x_tolerance=x_tolerance,
            )

            used_indexes: set[int] = set()
            matched: list[tuple[dict[str, Any], tuple[float, float, float, float]]] = []
            for caption in captions:
                chosen = choose_bbox_for_caption(tuple(caption["bbox"]), bboxes, used_indexes)
                if chosen is None:
                    continue
                bbox_index, bbox = chosen
                used_indexes.add(bbox_index)
                matched.append((caption, bbox))

            if include_uncaptioned:
                for bbox_index, bbox in enumerate(bboxes):
                    if bbox_index not in used_indexes:
                        matched.append(({}, bbox))

            for table_index, (caption, bbox) in enumerate(matched, start=1):
                table_id = caption.get("table_id") or f"table-{page_index}-{table_index}"
                filename = f"page_{page_index:03d}_{clean_filename(table_id)}_{table_index}.png"
                image_path = out_dir / filename
                width, height = render_crop(fitz, page, bbox, image_path, zoom, padding)
                records.append(
                    {
                        "table_id": table_id,
                        "page": page_index,
                        "image_path": str(image_path),
                        "caption": caption.get("caption", ""),
                        "extraction_method": "pymupdf_find_tables_crop",
                        "bbox": [round(value, 2) for value in bbox],
                        "width": width,
                        "height": height,
                    }
                )

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract cropped table images and metadata from a PDF.",
    )
    parser.add_argument("paper_pdf", help="Path to the input paper PDF")
    parser.add_argument(
        "--out-dir",
        default="tables",
        help="Directory for cropped table images (default: tables)",
    )
    parser.add_argument(
        "--metadata",
        default="tables/metadata.json",
        help="Output metadata JSON path (default: tables/metadata.json)",
    )
    parser.add_argument("--zoom", type=float, default=3.0, help="Render zoom for table crops")
    parser.add_argument("--padding", type=float, default=2.0, help="Padding in PDF points around table bbox")
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=18.0,
        help="Merge vertically adjacent detected table fragments within this gap",
    )
    parser.add_argument(
        "--x-tolerance",
        type=float,
        default=8.0,
        help="Horizontal tolerance for merging adjacent table fragments",
    )
    parser.add_argument(
        "--include-uncaptioned",
        action="store_true",
        help="Also output detected table-like regions without Table captions",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf_path = Path(args.paper_pdf)
    if not pdf_path.exists():
        fail(f"input PDF not found: {pdf_path}")
    if not pdf_path.is_file():
        fail(f"input path is not a file: {pdf_path}")
    if args.zoom <= 0:
        fail("--zoom must be positive")
    if args.padding < 0:
        fail("--padding must be non-negative")

    records = extract_tables(
        pdf_path=pdf_path,
        out_dir=Path(args.out_dir),
        metadata_path=Path(args.metadata),
        zoom=args.zoom,
        padding=args.padding,
        merge_gap=args.merge_gap,
        x_tolerance=args.x_tolerance,
        include_uncaptioned=args.include_uncaptioned,
    )
    print(f"wrote {len(records)} table crops to {args.out_dir}")
    print(f"wrote metadata to {args.metadata}")


if __name__ == "__main__":
    main()
