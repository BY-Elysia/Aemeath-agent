from __future__ import annotations

import json
import html
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol
from urllib.parse import urljoin, urlparse
from urllib.request import url2pathname

import httpx

from ..ark_client import ArkClient
from ..errors import ToolExecutionError
from ..tool_executor import ToolExecutionRecord, ToolExecutor
from .base import Capability, CapabilityContext, ToolSpec

if TYPE_CHECKING:
    from ..config import AppConfig


DEFAULT_MAX_PAGES = 8
MAX_MAX_PAGES = 80
MAX_SOURCE_CHARS = 30000
MAX_MARKDOWN_CHARS = 12000
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LLM_PAPER_READER_SKILL_DIR = PROJECT_ROOT / ".agents" / "skills" / "llm-paper-reader"
LLM_PAPER_READER_REFERENCE_FILES = (
    "references/output_templates.md",
    "references/reader_model_and_pedagogy.md",
    "references/mechanism_depth.md",
    "references/formula_explanation.md",
    "references/pseudocode_guide.md",
    "references/experiment_checklist.md",
    "references/limitations_future_work.md",
)
MAX_SKILL_PROMPT_CHARS = 22000


class PaperArkClient(Protocol):
    def create_response(self, prompt: str, tools: list[dict[str, Any]]) -> Any:
        raise NotImplementedError


TextExtractor = Callable[[Path, int], str]
PdfDownloader = Callable[[str, str], tuple[Path, str]]


@dataclass(frozen=True)
class PaperSource:
    file_path: Path
    label: str
    url: str


class PaperReaderCapability(Capability):
    name = "paper_reader"
    description = "Read a paper with the llm-paper-reader SKILL.md workflow, generate a Chinese Markdown report, and create a Feishu document."

    def __init__(
        self,
        config: AppConfig,
        executor: ToolExecutor,
        *,
        ark_client: PaperArkClient | None = None,
        text_extractor: TextExtractor | None = None,
        pdf_downloader: PdfDownloader | None = None,
    ) -> None:
        self._config = config
        self._executor = executor
        self._ark_client = ark_client or ArkClient(
            api_key=config.ark_api_key,
            base_url=config.ark_base_url,
            model=config.ark_model,
        )
        self._text_extractor = text_extractor or extract_pdf_text
        self._pdf_downloader = pdf_downloader or self._download_pdf
        self._download_dir = Path(config.app_db_path).parent / "paper_reader"
        self._skill_dir = LLM_PAPER_READER_SKILL_DIR

    def get_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="read_paper_url_to_feishu_doc",
                description=(
                    "Read a paper from a direct PDF URL, DOI URL, arXiv URL, or uploaded local PDF path, "
                    "generate a Markdown paper-reading report, and create a Feishu document with that Markdown body."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Feishu document title, for example 'DigimonGPT 论文阅读报告'.",
                        },
                        "paper_url": {
                            "type": "string",
                            "description": "Direct PDF URL, DOI URL, arXiv abs/pdf URL, or local file:// PDF path.",
                        },
                        "focus": {
                            "type": "string",
                            "description": "Optional user focus, such as agent memory, experiments, or implementation details.",
                        },
                        "max_pages": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": MAX_MAX_PAGES,
                            "default": DEFAULT_MAX_PAGES,
                            "description": "Maximum number of PDF pages to read.",
                        },
                        "send_as": {
                            "type": "string",
                            "enum": ["bot"],
                            "default": "bot",
                            "description": "Identity. Docs are created by bot; lark-cli grants the current CLI user access.",
                        },
                    },
                    "required": ["title", "paper_url"],
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        ]

    def get_guidance(self) -> str:
        return (
            "paper_reader capability:\n"
            "- 当用户在飞书里发论文 PDF、PDF 附件、DOI、arXiv 链接或论文网址，并要求阅读、总结、精读或生成飞书文档时，调用 read_paper_url_to_feishu_doc。\n"
            "- 运行时报告要求来自仓库内 .agents/skills/llm-paper-reader/SKILL.md，不要只做摘要或翻译。\n"
            "- 报告应讲清问题、全局架构、关键机制、公式、伪代码、实验、局限和复现路线。\n"
            "- title 要适合作为飞书文档标题，例如“DigimonGPT 论文阅读报告”。focus 可填写用户关心的问题或阅读角度。\n"
            "- 该工具会创建飞书文档，属于写操作，必须进入确认流；确认前不要说文档已经创建。\n"
        )

    def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: CapabilityContext,
    ) -> tuple[dict[str, Any], ToolExecutionRecord]:
        if tool_name != "read_paper_url_to_feishu_doc":
            raise ToolExecutionError("parameter_error", f"unsupported paper reader tool: {tool_name}")

        started = time.perf_counter()
        title = str(args.get("title") or "").strip()
        paper_url = str(args.get("paper_url") or "").strip()
        if not title:
            raise ToolExecutionError("parameter_error", "title is required")
        if not paper_url:
            raise ToolExecutionError("parameter_error", "paper_url is required")

        max_pages = self._normalize_max_pages(args.get("max_pages"))
        focus = str(args.get("focus") or "").strip()
        file_path, normalized_url = self._pdf_downloader(paper_url, context.session_id)
        source = PaperSource(file_path=file_path, label=file_path.name, url=normalized_url)

        paper_text = self._text_extractor(source.file_path, max_pages).strip()
        if not paper_text:
            raise ToolExecutionError("tool_error", f"未能从 PDF 中抽取到文本: {source.label}")

        markdown = self._generate_markdown(
            title=title,
            source=source,
            source_text=self._truncate_text(paper_text, MAX_SOURCE_CHARS),
            focus=focus,
            max_pages=max_pages,
        )
        doc_result, doc_record = self._executor.execute(
            "create_doc",
            {
                "title": title,
                "markdown": markdown,
                "send_as": "bot",
            },
        )
        result = {
            "title": title,
            "paperUrl": normalized_url,
            "sourceLabel": source.label,
            "maxPages": max_pages,
            "markdownChars": len(markdown),
            "markdownPreview": markdown[:600],
            "document": doc_result.get("document", doc_result),
        }
        duration_ms = int((time.perf_counter() - started) * 1000)
        command = [
            "paper-reader",
            "read-url",
            normalized_url,
            "->",
            "docs",
            "+create",
            "--title",
            title,
            "--markdown",
            "<generated-markdown>",
            "--as",
            "bot",
        ]
        return result, ToolExecutionRecord(
            tool_name=tool_name,
            command=command,
            stdout=json.dumps(result, ensure_ascii=False),
            stderr=doc_record.stderr,
            duration_ms=duration_ms,
            ok=True,
            error_category=None,
        )

    def _download_pdf(self, raw_url: str, session_id: str) -> tuple[Path, str]:
        normalized_url = self._normalize_paper_url(raw_url)
        local_path = self._resolve_local_pdf_path(normalized_url)
        if local_path is not None:
            return local_path, local_path.as_uri()

        parsed = urlparse(normalized_url)
        if parsed.scheme not in {"http", "https"}:
            raise ToolExecutionError("parameter_error", "paper_url must be an http(s) URL")

        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                response = client.get(normalized_url)
                response.raise_for_status()
                content = response.content
                content_type = str(response.headers.get("content-type") or "").lower()
                suffix = Path(urlparse(str(response.url)).path).suffix.lower()
                if not self._looks_like_pdf_response(content, content_type, suffix):
                    pdf_url = self._extract_pdf_url_from_html(response.text, str(response.url))
                    if not pdf_url:
                        raise ToolExecutionError(
                            "parameter_error",
                            "paper_url did not point to a PDF and no PDF link was found on the page",
                        )
                    normalized_url = pdf_url
                    response = client.get(pdf_url)
                    response.raise_for_status()
                    content = response.content
                    content_type = str(response.headers.get("content-type") or "").lower()
                    suffix = Path(urlparse(str(response.url)).path).suffix.lower()
        except httpx.HTTPError as exc:
            raise ToolExecutionError("tool_error", f"论文 URL 下载失败: {exc}") from exc

        if not content:
            raise ToolExecutionError("tool_error", "paper_url returned an empty response")
        if not self._looks_like_pdf_response(content, content_type, suffix):
            raise ToolExecutionError("parameter_error", "paper_url must point to a PDF file")

        file_name = Path(urlparse(str(response.url)).path).name or Path(parsed.path).name or "paper.pdf"
        if Path(file_name).suffix.lower() != ".pdf":
            file_name = f"{Path(file_name).stem or 'paper'}.pdf"
        session_dir = self._download_dir / self._sanitize_path_segment(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        file_path = session_dir / f"url_{uuid.uuid4().hex[:10]}_{self._sanitize_file_name(file_name)}"
        file_path.write_bytes(content)
        return file_path, normalized_url

    def _generate_markdown(
        self,
        *,
        title: str,
        source: PaperSource,
        source_text: str,
        focus: str,
        max_pages: int,
    ) -> str:
        prompt = self._build_prompt(
            title=title,
            source=source,
            source_text=source_text,
            focus=focus,
            max_pages=max_pages,
        )
        try:
            response = self._ark_client.create_response(prompt, [])
        except Exception as exc:
            raise ToolExecutionError(
                "tool_error",
                f"Ark 论文阅读报告生成失败: {exc}",
                {
                    "command": ["ark", "responses.create", "--model", self._config.ark_model],
                    "stderr": str(exc),
                    "duration_ms": 0,
                },
            ) from exc
        markdown = self._extract_response_text(response)
        if not markdown:
            raise ToolExecutionError("tool_error", "Ark did not return Markdown content")
        markdown = self._strip_outer_markdown_fence(markdown)
        if not markdown.lstrip().startswith("#"):
            markdown = f"# {title}\n\n{markdown}"
        return self._truncate_markdown(markdown)

    def _build_prompt(
        self,
        *,
        title: str,
        source: PaperSource,
        source_text: str,
        focus: str,
        max_pages: int,
    ) -> str:
        focus_line = f"\n用户关注点：{focus}\n" if focus else "\n用户关注点：未特别指定，请按 llm-paper-reader 默认深度阅读。\n"
        skill_prompt = self._load_llm_paper_reader_prompt()
        return (
            "你正在作为仓库内 llm-paper-reader skill 执行论文阅读任务。下面的 SKILL.md 和 reference 摘要是强约束，"
            "最终输出必须是一份正式中文 Markdown 论文讲解报告，而不是普通摘要、翻译或聊天回复。\n\n"
            "【llm-paper-reader skill instructions】\n"
            f"{skill_prompt}\n\n"
            "【当前飞书工具运行约束】\n"
            "- 最终 Markdown 会写入飞书文档，不要输出原始日志、证据索引或工具调用细节。\n"
            "- 当前自动化链路主要提供 PDF 正文抽取；如果没有可嵌入的原图或表格资源，不要伪造图表，直接说明原文图表需回看 PDF。\n"
            "- 只依据论文正文和明确的用户关注点写作。原文未提供的信息写“原文未明确说明”。\n"
            "- 控制在 5000 到 9000 个中文字符左右，不要把整篇输出包在代码块里。\n\n"
            "【本次报告标题】\n"
            f"# {title}\n"
            f"{focus_line}"
            f"\n来源 URL：{source.url}\n"
            f"来源文件：{source.label}\n"
            f"已读取页数上限：{max_pages}\n"
            "\n论文正文节选如下：\n"
            "<<<PAPER_TEXT\n"
            f"{source_text}\n"
            "PAPER_TEXT>>>\n"
        )

    def _load_llm_paper_reader_prompt(self) -> str:
        if not self._skill_dir.exists():
            return (
                "llm-paper-reader/SKILL.md 未安装。退回基础要求：生成严谨中文论文阅读报告，覆盖问题、架构、机制、公式、实验、局限和复现路线。"
            )

        parts = [self._strip_frontmatter(self._read_skill_resource("SKILL.md")).strip()]
        for relative_path in LLM_PAPER_READER_REFERENCE_FILES:
            content = self._read_skill_resource(relative_path).strip()
            if content:
                parts.append(f"## {relative_path}\n{content}")

        merged = "\n\n".join(part for part in parts if part)
        return self._truncate_text(merged, MAX_SKILL_PROMPT_CHARS)

    def _read_skill_resource(self, relative_path: str) -> str:
        path = self._skill_dir / relative_path
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    @staticmethod
    def _strip_frontmatter(markdown: str) -> str:
        value = markdown.strip()
        if not value.startswith("---"):
            return value
        match = re.match(r"^---\s*\n.*?\n---\s*\n(?P<body>.*)$", value, flags=re.DOTALL)
        return match.group("body").strip() if match else value

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        if isinstance(response, str):
            return response.strip()
        if isinstance(response, dict):
            return str(response.get("text") or response.get("output_text") or "").strip()
        return str(getattr(response, "text", "") or "").strip()

    @staticmethod
    def _strip_outer_markdown_fence(text: str) -> str:
        value = text.strip()
        match = re.fullmatch(r"```(?:markdown|md)?\s*\n(?P<body>.*)\n```", value, flags=re.DOTALL | re.IGNORECASE)
        if match:
            return match.group("body").strip()
        return value

    @staticmethod
    def _truncate_markdown(markdown: str) -> str:
        if len(markdown) <= MAX_MARKDOWN_CHARS:
            return markdown
        return (
            markdown[:MAX_MARKDOWN_CHARS].rstrip()
            + "\n\n> 注：由于飞书文档创建参数长度限制，本次报告已自动截断。建议缩小 max_pages 或聚焦一个章节后重新生成。"
        )

    @staticmethod
    def _truncate_text(text: str, limit: int) -> str:
        value = text.strip()
        if len(value) <= limit:
            return value
        return value[:limit].rstrip() + "\n\n[Source text truncated]"

    @staticmethod
    def _normalize_max_pages(value: Any) -> int:
        try:
            pages = int(value) if value is not None else DEFAULT_MAX_PAGES
        except (TypeError, ValueError):
            raise ToolExecutionError("parameter_error", "max_pages must be an integer") from None
        if pages < 1:
            return 1
        return min(pages, MAX_MAX_PAGES)

    @staticmethod
    def _normalize_paper_url(raw_url: str) -> str:
        url = str(raw_url or "").strip()
        doi_url = re.match(r"^(?:doi:\s*)?(?P<doi>10\.\d{4,9}/\S+)$", url, flags=re.IGNORECASE)
        if doi_url:
            return f"https://doi.org/{doi_url.group('doi')}"
        arxiv_abs = re.match(r"^https?://arxiv\.org/abs/(?P<paper_id>[^?#/]+)", url)
        if arxiv_abs:
            return f"https://arxiv.org/pdf/{arxiv_abs.group('paper_id')}.pdf"
        arxiv_pdf = re.match(r"^https?://arxiv\.org/pdf/(?P<paper_id>[^?#/]+?)(?:\.pdf)?(?:[?#].*)?$", url)
        if arxiv_pdf:
            return f"https://arxiv.org/pdf/{arxiv_pdf.group('paper_id')}.pdf"
        return url

    @staticmethod
    def _resolve_local_pdf_path(raw_url: str) -> Path | None:
        parsed = urlparse(str(raw_url or "").strip())
        if parsed.scheme == "file":
            if parsed.netloc:
                path = Path(f"//{parsed.netloc}{url2pathname(parsed.path)}")
            else:
                path = Path(url2pathname(parsed.path))
        elif not parsed.scheme:
            path = Path(str(raw_url or "").strip()).expanduser()
        else:
            return None

        path = path.resolve()
        if not path.exists() or not path.is_file():
            raise ToolExecutionError("parameter_error", f"local PDF file not found: {path}")
        if path.suffix.lower() != ".pdf" and not path.read_bytes().startswith(b"%PDF"):
            raise ToolExecutionError("parameter_error", f"local file is not a PDF: {path}")
        return path

    @staticmethod
    def _looks_like_pdf_response(content: bytes, content_type: str, suffix: str) -> bool:
        return suffix == ".pdf" or "pdf" in content_type.lower() or content.startswith(b"%PDF")

    @staticmethod
    def _extract_pdf_url_from_html(page_text: str, base_url: str) -> str | None:
        candidates: list[str] = []
        patterns = [
            r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_pdf_url["\']',
            r'href=["\']([^"\']*\.pdf(?:[?#][^"\']*)?)["\']',
            r'href=["\']([^"\']*(?:/download/|/article/download/)[^"\']*)["\']',
        ]
        for pattern in patterns:
            candidates.extend(re.findall(pattern, page_text, flags=re.IGNORECASE))

        for candidate in candidates:
            value = html.unescape(str(candidate or "").strip())
            if not value:
                continue
            return urljoin(base_url, value)
        return None

    @staticmethod
    def _sanitize_path_segment(value: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
        return sanitized[:80] or "session"

    @staticmethod
    def _sanitize_file_name(value: str) -> str:
        name = Path(str(value or "paper.pdf")).name
        sanitized = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
        return sanitized or "paper.pdf"


def extract_pdf_text(pdf_path: Path, max_pages: int) -> str:
    fitz_error: Exception | None = None
    try:
        import fitz  # type: ignore[import-not-found]

        document = fitz.open(str(pdf_path))
        try:
            pages = []
            page_count = min(len(document), max(1, int(max_pages)))
            for page_index in range(page_count):
                text = document.load_page(page_index).get_text("text").strip()
                if text:
                    pages.append(f"\n\n--- Page {page_index + 1} ---\n{text}")
            return "\n".join(pages).strip()
        finally:
            document.close()
    except ImportError:
        pass
    except Exception as exc:
        fitz_error = exc

    pdftotext_bin = shutil.which("pdftotext")
    if pdftotext_bin:
        try:
            result = subprocess.run(
                [
                    pdftotext_bin,
                    "-f",
                    "1",
                    "-l",
                    str(max(1, int(max_pages))),
                    "-layout",
                    str(pdf_path),
                    "-",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ToolExecutionError("tool_error", f"PDF 文本抽取失败: {exc}") from exc
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        detail = result.stderr.strip() or "pdftotext returned empty text"
        if fitz_error is not None:
            detail = f"PyMuPDF failed: {fitz_error}; pdftotext failed: {detail}"
        raise ToolExecutionError("tool_error", f"PDF 文本抽取失败: {detail}")

    if fitz_error is not None:
        raise ToolExecutionError("tool_error", f"PDF 文本抽取失败: {fitz_error}") from fitz_error
    raise ToolExecutionError("tool_error", "PDF 文本抽取失败：请安装 PyMuPDF 或 pdftotext。")
