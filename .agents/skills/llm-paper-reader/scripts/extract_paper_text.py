#!/usr/bin/env python3
"""Extract page-numbered Markdown text from a paper PDF."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def fail(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_with_pymupdf(pdf_path: Path) -> tuple[list[str], dict[str, str]]:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is not installed") from exc

    pages: list[str] = []
    metadata: dict[str, str] = {}
    with fitz.open(pdf_path) as doc:
        metadata = {str(k): str(v) for k, v in (doc.metadata or {}).items() if v}
        for page in doc:
            pages.append(page.get_text("text", sort=True).strip())
    return pages, metadata


def load_with_pdfplumber(pdf_path: Path) -> tuple[list[str], dict[str, str]]:
    try:
        import pdfplumber  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pdfplumber is not installed") from exc

    pages: list[str] = []
    metadata: dict[str, str] = {}
    with pdfplumber.open(str(pdf_path)) as pdf:
        metadata = {str(k): str(v) for k, v in (pdf.metadata or {}).items() if v}
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            pages.append(text.strip())
    return pages, metadata


def extract_pages(pdf_path: Path) -> tuple[list[str], dict[str, str], str]:
    errors: list[str] = []
    for loader_name, loader in (
        ("PyMuPDF", load_with_pymupdf),
        ("pdfplumber", load_with_pdfplumber),
    ):
        try:
            pages, metadata = loader(pdf_path)
            return pages, metadata, loader_name
        except RuntimeError as exc:
            errors.append(str(exc))
        except Exception as exc:  # noqa: BLE001 - CLI should report parser failures clearly.
            errors.append(f"{loader_name} failed: {exc}")

    joined = "; ".join(errors)
    fail(
        "could not extract PDF text. Install a supported parser with "
        "`python3 -m pip install pymupdf pdfplumber`. Details: "
        f"{joined}"
    )


def markdown_escape(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def write_markdown(
    out_path: Path,
    pdf_path: Path,
    pages: list[str],
    metadata: dict[str, str],
    parser_name: str,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Extracted Paper Text",
        "",
        f"- Source: `{pdf_path}`",
        f"- Parser: {parser_name}",
        f"- Pages: {len(pages)}",
    ]

    useful_metadata = {
        key: metadata[key]
        for key in ("title", "author", "subject", "keywords", "creationDate", "modDate")
        if key in metadata
    }
    if useful_metadata:
        lines.append("")
        lines.append("## PDF Metadata")
        lines.append("")
        for key, value in useful_metadata.items():
            lines.append(f"- {key}: {markdown_escape(value)}")

    for index, text in enumerate(pages, start=1):
        lines.append("")
        lines.append(f"## Page {index}")
        lines.append("")
        lines.append(markdown_escape(text) if text else "[No extractable text on this page]")

    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract page-numbered Markdown text from a paper PDF.",
    )
    parser.add_argument("paper_pdf", help="Path to the input paper PDF")
    parser.add_argument(
        "--out",
        default="paper_text.md",
        help="Output Markdown path (default: paper_text.md)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf_path = Path(args.paper_pdf)
    out_path = Path(args.out)

    if not pdf_path.exists():
        fail(f"input PDF not found: {pdf_path}")
    if not pdf_path.is_file():
        fail(f"input path is not a file: {pdf_path}")

    pages, metadata, parser_name = extract_pages(pdf_path)
    write_markdown(out_path, pdf_path, pages, metadata, parser_name)
    print(f"wrote {len(pages)} pages to {out_path}")


if __name__ == "__main__":
    main()
