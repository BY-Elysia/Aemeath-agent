from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from feishu_agent.config import AppConfig
from feishu_agent.errors import ToolExecutionError
from feishu_agent.capabilities.base import CapabilityContext
from feishu_agent.capabilities.paper_reader import PaperReaderCapability
from feishu_agent.tool_executor import ToolExecutionRecord, summarize_pending_action


def make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        ark_api_key="test-key",
        ark_base_url="https://ark.cn-beijing.volces.com/api/v3",
        ark_model="ep-test",
        lark_cli_bin="lark-cli",
        app_db_path=tmp_path / "app.db",
        command_timeout_seconds=10,
        max_history_messages=20,
        max_tool_round_trips=4,
        feishu_agent_base_url="http://127.0.0.1:8000",
        auto_reply_p2p_only=True,
        group_reply_mode="off",
        bot_mention_ids=(),
        bot_mention_names=(),
        agent_persona="aemeath",
        enabled_capabilities=("paper_reader",),
        enabled_agent_skills=("feishu-agent-workflows",),
    )


class FakeArkClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.tools: list[list[dict[str, Any]]] = []

    def create_response(self, prompt: str, tools: list[dict[str, Any]]) -> SimpleNamespace:
        self.prompts.append(prompt)
        self.tools.append(tools)
        return SimpleNamespace(text="# Demo Paper\n\n## 1. 论文信息与一句话概括\n测试 Markdown")


class FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, tool_name: str, args: dict[str, Any]) -> tuple[dict[str, Any], ToolExecutionRecord]:
        self.calls.append((tool_name, dict(args)))
        return (
            {"document": {"url": "https://feishu.example/doc", "title": args["title"]}},
            ToolExecutionRecord(
                tool_name=tool_name,
                command=["docs", "+create", "--title", args["title"], "--markdown", "<body>", "--as", "user"],
                stdout="{}",
                stderr="",
                duration_ms=7,
                ok=True,
            ),
        )


def test_paper_reader_capability_tool_is_confirmation_only(tmp_path: Path) -> None:
    skill = PaperReaderCapability(
        make_config(tmp_path),
        FakeExecutor(),  # type: ignore[arg-type]
        ark_client=FakeArkClient(),
        text_extractor=lambda _path, _max_pages: "paper text",
        pdf_downloader=lambda _url, _session_id: (tmp_path / "paper.pdf", "https://example.com/paper.pdf"),
    )

    tools = {tool.name: tool for tool in skill.get_tools()}

    assert tools["read_paper_url_to_feishu_doc"].requires_confirmation is True
    assert tools["read_paper_url_to_feishu_doc"].parameters["required"] == ["title", "paper_url"]


def test_paper_reader_capability_generates_markdown_and_creates_doc_from_url(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    ark_client = FakeArkClient()
    executor = FakeExecutor()
    extracted: list[tuple[Path, int]] = []

    def fake_extract(path: Path, max_pages: int) -> str:
        extracted.append((path, max_pages))
        return "Paper title\nMethod: hierarchical memory. Experiments are strong."

    skill = PaperReaderCapability(
        config,
        executor,  # type: ignore[arg-type]
        ark_client=ark_client,
        text_extractor=fake_extract,
        pdf_downloader=lambda _url, _session_id: (pdf_path, "https://arxiv.org/pdf/1234.5678.pdf"),
    )

    result, record = skill.execute(
        "read_paper_url_to_feishu_doc",
        {
            "title": "Demo Paper 阅读报告",
            "paper_url": "https://arxiv.org/abs/1234.5678",
            "focus": "重点关注 agent memory",
            "max_pages": 3,
        },
        CapabilityContext(session_id="im-chat:oc_1", source="test"),
    )

    assert extracted == [(pdf_path, 3)]
    assert "hierarchical memory" in ark_client.prompts[0]
    assert "重点关注 agent memory" in ark_client.prompts[0]
    assert ark_client.tools == [[]]
    assert executor.calls[0][0] == "create_doc"
    assert executor.calls[0][1]["title"] == "Demo Paper 阅读报告"
    assert executor.calls[0][1]["markdown"].startswith("# Demo Paper")
    assert result["document"]["url"] == "https://feishu.example/doc"
    assert result["paperUrl"] == "https://arxiv.org/pdf/1234.5678.pdf"
    assert result["markdownChars"] == len(executor.calls[0][1]["markdown"])
    assert record.tool_name == "read_paper_url_to_feishu_doc"
    assert "<generated-markdown>" in record.command


def test_paper_reader_prompt_loads_llm_paper_reader_skill(tmp_path: Path) -> None:
    skill = PaperReaderCapability(
        make_config(tmp_path),
        FakeExecutor(),  # type: ignore[arg-type]
        ark_client=FakeArkClient(),
        text_extractor=lambda _path, _max_pages: "paper text",
        pdf_downloader=lambda _url, _session_id: (tmp_path / "paper.pdf", "https://example.com/paper.pdf"),
    )

    prompt = skill._build_prompt(
        title="Demo Paper 论文阅读报告",
        source=type("Source", (), {"url": "https://example.com/paper.pdf", "label": "paper.pdf"})(),
        source_text="Abstract. Method. Experiments.",
        focus="agent memory",
        max_pages=3,
    )

    assert "LLM Paper Reader" in prompt
    assert "references/output_templates.md" in prompt
    assert "正式中文 Markdown 论文讲解报告" in prompt


def test_paper_reader_capability_rejects_missing_url(tmp_path: Path) -> None:
    skill = PaperReaderCapability(
        make_config(tmp_path),
        FakeExecutor(),  # type: ignore[arg-type]
        ark_client=FakeArkClient(),
        text_extractor=lambda _path, _max_pages: "paper text",
        pdf_downloader=lambda _url, _session_id: (tmp_path / "paper.pdf", "https://example.com/paper.pdf"),
    )

    with pytest.raises(ToolExecutionError) as exc_info:
        skill.execute(
            "read_paper_url_to_feishu_doc",
            {"title": "No URL"},
            CapabilityContext(session_id="s1", source="test"),
        )

    assert exc_info.value.category == "parameter_error"
    assert "paper_url" in exc_info.value.message


def test_paper_reader_capability_normalizes_arxiv_urls() -> None:
    assert (
        PaperReaderCapability._normalize_paper_url("https://arxiv.org/abs/1234.5678")
        == "https://arxiv.org/pdf/1234.5678.pdf"
    )
    assert (
        PaperReaderCapability._normalize_paper_url("https://arxiv.org/pdf/1234.5678")
        == "https://arxiv.org/pdf/1234.5678.pdf"
    )
    assert (
        PaperReaderCapability._normalize_paper_url("doi:10.1609/aaai.v40i8.37523")
        == "https://doi.org/10.1609/aaai.v40i8.37523"
    )


def test_paper_reader_capability_accepts_local_file_uri(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    skill = PaperReaderCapability(
        make_config(tmp_path),
        FakeExecutor(),  # type: ignore[arg-type]
        ark_client=FakeArkClient(),
    )

    local_path, normalized = skill._download_pdf(pdf_path.as_uri(), "session-1")

    assert local_path == pdf_path
    assert normalized == pdf_path.as_uri()


def test_paper_reader_capability_extracts_pdf_url_from_html() -> None:
    html = """
    <html><head>
      <meta name="citation_pdf_url" content="/papers/demo.pdf">
    </head></html>
    """

    assert (
        PaperReaderCapability._extract_pdf_url_from_html(html, "https://example.com/article/1")
        == "https://example.com/papers/demo.pdf"
    )


def test_paper_reader_capability_pending_summary() -> None:
    summary, preview = summarize_pending_action(
        "read_paper_url_to_feishu_doc",
        {
            "title": "Demo Paper 阅读报告",
            "paper_url": "https://arxiv.org/abs/1234.5678",
            "focus": "memory",
            "max_pages": 5,
        },
    )

    assert "阅读论文" in summary
    assert preview["title"] == "Demo Paper 阅读报告"
    assert preview["paper_url"] == "https://arxiv.org/abs/1234.5678"
    assert preview["max_pages"] == 5
