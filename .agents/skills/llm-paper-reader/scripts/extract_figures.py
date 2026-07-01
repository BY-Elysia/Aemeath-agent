#!/usr/bin/env python3
"""Extract candidate paper figures and metadata from a PDF."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CAPTION_RE = re.compile(
    r"^\s*(?P<label>Fig(?:ure)?\.?)\s*(?P<number>[A-Za-z0-9][A-Za-z0-9.\-]*)\s*[:.\-]?\s*(?P<caption>.*)$",
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
            "extract_figures.py requires PyMuPDF. Install it with "
            "`python3 -m pip install pymupdf`."
        )
    return fitz


def clean_filename(value: str) -> str:
    value = value.lower().replace(".", "")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "figure"


def likely_type(caption: str) -> str:
    text = caption.lower()
    checks = [
        ("architecture", ("architecture", "framework", "overview", "module", "transformer", "attention", "network")),
        ("training", ("training", "train", "pretrain", "fine-tune", "finetune", "optimization", "loss", "rlhf", "preference")),
        ("inference", ("inference", "decoding", "generation", "serving", "sampling")),
        ("data-flow", ("data", "dataset", "pipeline", "construction", "retrieval", "corpus")),
        ("system", ("system", "deployment", "latency", "throughput", "memory", "cache")),
        ("evaluation", ("benchmark", "result", "performance", "comparison", "qualitative", "case study")),
    ]
    for label, keywords in checks:
        if any(keyword in text for keyword in keywords):
            return label
    return "figure"


def line_records(page: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for block in page.get_text("dict", sort=True).get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
            if text:
                records.append(
                    {
                        "text": text,
                        "bbox": tuple(float(value) for value in line.get("bbox", (0, 0, 0, 0))),
                    }
                )
    return records


def page_captions(page: Any) -> list[dict[str, Any]]:
    captions: list[dict[str, Any]] = []
    lines = line_records(page)
    index = 0
    while index < len(lines):
        match = CAPTION_RE.match(str(lines[index]["text"]).rstrip())
        if not match:
            index += 1
            continue

        figure_id = f"Fig. {match.group('number').rstrip('.-')}"
        caption_parts = [match.group("caption").strip()]
        caption_bbox = list(lines[index]["bbox"])
        lookahead = index + 1
        while lookahead < len(lines):
            candidate = str(lines[lookahead]["text"]).strip()
            previous_bbox = tuple(lines[lookahead - 1]["bbox"])
            candidate_bbox = tuple(lines[lookahead]["bbox"])
            if not candidate:
                break
            if float(candidate_bbox[1]) - float(previous_bbox[3]) > 5:
                break
            if CAPTION_RE.match(candidate) or re.match(r"^(Table|Algorithm)\s+", candidate, re.IGNORECASE):
                break
            if re.match(
                r"^(Abstract|Introduction|References|Acknowledg(?:e)?ments|Appendix)\b",
                candidate,
                re.IGNORECASE,
            ):
                break
            if re.match(r"^\d+(?:\.\d+)*\.?\s+\S+", candidate):
                break
            if len(" ".join(caption_parts + [candidate])) > 600:
                break
            caption_parts.append(candidate)
            caption_bbox[0] = min(caption_bbox[0], candidate_bbox[0])
            caption_bbox[1] = min(caption_bbox[1], candidate_bbox[1])
            caption_bbox[2] = max(caption_bbox[2], candidate_bbox[2])
            caption_bbox[3] = max(caption_bbox[3], candidate_bbox[3])
            lookahead += 1

        caption = " ".join(part for part in caption_parts if part).strip()
        captions.append(
            {
                "figure_id": figure_id,
                "caption": caption,
                "likely_type": likely_type(caption),
                "bbox": caption_bbox,
            }
        )
        index = max(lookahead, index + 1)
    return captions


def save_pixmap_as_png(fitz: Any, doc: Any, xref: int, image_path: Path) -> tuple[int, int]:
    pix = fitz.Pixmap(doc, xref)
    try:
        if pix.n - pix.alpha >= 4:
            converted = fitz.Pixmap(fitz.csRGB, pix)
            pix = converted
        image_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(image_path))
        return pix.width, pix.height
    finally:
        pix = None


def render_page(fitz: Any, page: Any, image_path: Path, zoom: float) -> tuple[int, int]:
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(image_path))
    return pix.width, pix.height


def max_image_page_coverage(page: Any, xref: int) -> float:
    try:
        rects = page.get_image_rects(xref)
    except Exception:
        return 0.0
    page_area = max(1.0, float(page.rect.width * page.rect.height))
    coverages = [
        float((rect & page.rect).width * (rect & page.rect).height) / page_area
        for rect in rects
        if not (rect & page.rect).is_empty
    ]
    return max(coverages, default=0.0)


def rect_tuple(rect: Any) -> tuple[float, float, float, float]:
    return (float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3]))


def render_crop(
    fitz: Any,
    page: Any,
    bbox: tuple[float, float, float, float],
    image_path: Path,
    zoom: float,
    padding: float,
) -> tuple[int, int]:
    page_rect = page.rect
    rect = fitz.Rect(*bbox) & page_rect
    rect.x0 = max(page_rect.x0, rect.x0 - padding)
    rect.y0 = max(page_rect.y0, rect.y0 - padding)
    rect.x1 = min(page_rect.x1, rect.x1 + padding)
    rect.y1 = min(page_rect.y1, rect.y1 + padding)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(image_path))
    return pix.width, pix.height


def find_vector_figure_bbox(
    fitz: Any,
    page: Any,
    caption: dict[str, Any],
    previous_caption_bottom: float,
) -> tuple[float, float, float, float] | None:
    caption_rect = fitz.Rect(*caption["bbox"])
    page_rect = page.rect
    candidates: list[tuple[float, Any]] = []

    for drawing in page.get_drawings():
        rect = fitz.Rect(drawing["rect"]) & page_rect
        if rect.is_empty or rect.width < 40 or rect.height < 20:
            continue
        if rect.y0 < previous_caption_bottom - 4:
            continue
        if rect.y0 >= caption_rect.y0 or rect.y1 > caption_rect.y0 + 24:
            continue
        area = rect.width * rect.height
        candidates.append((area, rect))

    if not candidates:
        return None

    _, seed = max(candidates, key=lambda item: item[0])
    seed.y1 = min(seed.y1, caption_rect.y0 - 3)
    if seed.width < 80 or seed.height < 35:
        return None
    return rect_tuple(seed)


def extract_figures(
    pdf_path: Path,
    out_dir: Path,
    metadata_path: Path,
    min_width: int,
    min_height: int,
    render_caption_pages: bool,
    render_zoom: float,
    crop_padding: float,
    allow_full_page_fallback: bool,
) -> list[dict[str, Any]]:
    fitz = require_fitz()
    records: list[dict[str, Any]] = []

    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc, start=1):
            captions = page_captions(page)
            caption = captions[0] if captions else {}
            page_records = 0

            for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                xref = image_info[0]
                base_info = doc.extract_image(xref)
                width = int(base_info.get("width") or 0)
                height = int(base_info.get("height") or 0)
                if width < min_width or height < min_height:
                    continue

                figure_id = caption.get("figure_id") or f"image-{page_index}-{image_index}"
                filename = f"page_{page_index:03d}_{clean_filename(figure_id)}_{image_index}.png"
                image_path = out_dir / filename
                saved_width, saved_height = save_pixmap_as_png(fitz, doc, xref, image_path)
                page_coverage = max_image_page_coverage(page, xref)
                is_full_page_image = page_coverage >= 0.8
                records.append(
                    {
                        "figure_id": figure_id,
                        "page": page_index,
                        "image_path": str(image_path),
                        "caption": caption.get("caption", ""),
                        "likely_type": caption.get("likely_type") or likely_type(caption.get("caption", "")),
                        "extraction_method": (
                            "embedded_full_page_do_not_embed"
                            if is_full_page_image
                            else "embedded_image"
                        ),
                        "safe_to_embed": not is_full_page_image,
                        "requires_visual_review": True,
                        "page_coverage": round(page_coverage, 4),
                        "width": saved_width,
                        "height": saved_height,
                    }
                )
                page_records += 1

            if render_caption_pages and captions and page_records == 0:
                previous_caption_bottom = float(page.rect.y0)
                for caption_index, caption in enumerate(captions, start=1):
                    figure_id = caption["figure_id"]
                    bbox = find_vector_figure_bbox(
                        fitz,
                        page,
                        caption,
                        previous_caption_bottom=previous_caption_bottom,
                    )
                    if bbox is not None:
                        filename = f"page_{page_index:03d}_{clean_filename(figure_id)}_crop.png"
                        image_path = out_dir / filename
                        saved_width, saved_height = render_crop(
                            fitz,
                            page,
                            bbox,
                            image_path,
                            render_zoom,
                            crop_padding,
                        )
                        extraction_method = "vector_figure_crop"
                        safe_to_embed = True
                    elif allow_full_page_fallback:
                        filename = (
                            f"page_{page_index:03d}_{clean_filename(figure_id)}"
                            "_full_page_fallback.png"
                        )
                        image_path = out_dir / filename
                        saved_width, saved_height = render_page(fitz, page, image_path, render_zoom)
                        extraction_method = "full_page_fallback_do_not_embed"
                        safe_to_embed = False
                    else:
                        print(
                            f"warning: could not locate a crop for {figure_id} on page "
                            f"{page_index}; skipped instead of rendering a full page",
                            file=sys.stderr,
                        )
                        previous_caption_bottom = max(
                            previous_caption_bottom,
                            float(caption["bbox"][3]),
                        )
                        continue

                    records.append(
                        {
                            "figure_id": figure_id,
                            "page": page_index,
                            "image_path": str(image_path),
                            "caption": caption["caption"],
                            "likely_type": caption["likely_type"],
                            "extraction_method": extraction_method,
                            "safe_to_embed": safe_to_embed,
                            "requires_visual_review": True,
                            "bbox": [round(value, 2) for value in bbox] if bbox else None,
                            "width": saved_width,
                            "height": saved_height,
                        }
                    )
                    previous_caption_bottom = max(
                        previous_caption_bottom,
                        float(caption["bbox"][3]),
                    )

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract candidate paper figures and metadata from a PDF.",
    )
    parser.add_argument("paper_pdf", help="Path to the input paper PDF")
    parser.add_argument(
        "--out-dir",
        default="figures",
        help="Directory for extracted figure images (default: figures)",
    )
    parser.add_argument(
        "--metadata",
        default="figures/metadata.json",
        help="Output metadata JSON path (default: figures/metadata.json)",
    )
    parser.add_argument("--min-width", type=int, default=120, help="Minimum embedded image width")
    parser.add_argument("--min-height", type=int, default=120, help="Minimum embedded image height")
    parser.add_argument(
        "--no-render-caption-pages",
        action="store_true",
        help="Disable vector-figure crop rendering for pages with captions but no embedded image",
    )
    parser.add_argument("--render-zoom", type=float, default=2.0, help="Zoom for caption page renders")
    parser.add_argument(
        "--crop-padding",
        type=float,
        default=4.0,
        help="Padding in PDF points around vector figure crops",
    )
    parser.add_argument(
        "--allow-full-page-fallback",
        action="store_true",
        help="Write explicitly unsafe full-page fallback assets when a crop cannot be located",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf_path = Path(args.paper_pdf)
    if not pdf_path.exists():
        fail(f"input PDF not found: {pdf_path}")
    if not pdf_path.is_file():
        fail(f"input path is not a file: {pdf_path}")
    if args.render_zoom <= 0:
        fail("--render-zoom must be positive")
    if args.crop_padding < 0:
        fail("--crop-padding must be non-negative")

    records = extract_figures(
        pdf_path=pdf_path,
        out_dir=Path(args.out_dir),
        metadata_path=Path(args.metadata),
        min_width=args.min_width,
        min_height=args.min_height,
        render_caption_pages=not args.no_render_caption_pages,
        render_zoom=args.render_zoom,
        crop_padding=args.crop_padding,
        allow_full_page_fallback=args.allow_full_page_fallback,
    )
    print(f"wrote {len(records)} figure candidates to {args.out_dir}")
    print(f"wrote metadata to {args.metadata}")


if __name__ == "__main__":
    main()
