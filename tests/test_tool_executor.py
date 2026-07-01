from __future__ import annotations

import json
import os
from pathlib import Path

from feishu_agent.cli_runner import CommandResult
from feishu_agent.tool_executor import ToolExecutor


class DummyRunner:
    def run(self, args):
        raise AssertionError("not used")


def test_map_bot_availability_error() -> None:
    executor = ToolExecutor(DummyRunner())
    result = CommandResult(
        command=["lark-cli", "im", "+messages-send"],
        returncode=1,
        stdout='{"ok": false, "error": {"type": "api_error", "code": 230013, "message": "HTTP 400: Bot has NO availability to this user."}}',
        stderr="",
        duration_ms=5,
        parsed_json={"ok": False, "error": {"type": "api_error", "code": 230013, "message": "HTTP 400: Bot has NO availability to this user."}},
    )

    error = executor._map_error(result.parsed_json, result)
    assert error.category == "bot_availability"
    assert "availability" in error.message.lower()


def test_map_missing_scope_error() -> None:
    executor = ToolExecutor(DummyRunner())
    result = CommandResult(
        command=["lark-cli", "im", "+messages-search"],
        returncode=3,
        stdout='{"ok": false, "error": {"type": "missing_scope", "message": "missing required scope(s): search:message"}}',
        stderr="",
        duration_ms=5,
        parsed_json={"ok": False, "error": {"type": "missing_scope", "message": "missing required scope(s): search:message"}},
    )

    error = executor._map_error(result.parsed_json, result)
    assert error.category == "permission_denied"


def test_normalize_search_user_reads_data_wrapper() -> None:
    executor = ToolExecutor(DummyRunner())
    payload = executor._normalize_search_user(
        {
            "ok": True,
            "identity": "user",
            "data": {
                "users": [
                    {
                        "name": "周灿宇",
                        "open_id": "ou_xxx",
                        "email": "a@example.com",
                    }
                ],
                "has_more": False,
                "page_token": "",
            },
        }
    )

    assert payload["matches"] == [
        {
            "name": "周灿宇",
            "open_id": "ou_xxx",
            "email": "a@example.com",
            "mobile": None,
            "department": None,
            "enterprise_email": None,
        }
    ]


def test_normalize_search_messages_reads_data_wrapper() -> None:
    executor = ToolExecutor(DummyRunner())
    payload = executor._normalize_search_messages(
        {
            "ok": True,
            "identity": "user",
            "data": {
                "messages": [{"message_id": "om_xxx", "content": "你好"}],
                "total": 1,
                "has_more": False,
                "page_token": "",
            },
        }
    )

    assert payload["total"] == 1
    assert payload["messages"][0]["message_id"] == "om_xxx"


class RecordingRunner:
    def __init__(self, expected_markdown: str, image_path: Path | None = None) -> None:
        self.expected_markdown = expected_markdown
        self.image_path = image_path
        self.calls: list[tuple[list[str], Path | None]] = []

    def run(self, args, *, cwd=None):
        cwd_path = Path(cwd) if cwd is not None else None
        self.calls.append((list(args), cwd_path))
        if args[:2] == ["docs", "+create"]:
            assert "--markdown" in args
            markdown_arg = args[args.index("--markdown") + 1]
            assert markdown_arg == "@body.md"
            assert cwd_path is not None
            assert (cwd_path / "body.md").read_text(encoding="utf-8") == self.expected_markdown
            payload = {
                "ok": True,
                "data": {
                    "doc_id": "doc_token",
                    "doc_url": "https://www.feishu.cn/docx/doc_token",
                    "message": "文档创建成功",
                },
            }
            return CommandResult(
                command=["lark-cli", *args],
                returncode=0,
                stdout=json.dumps(payload, ensure_ascii=False),
                stderr="",
                duration_ms=5,
                parsed_json=payload,
            )
        if args[:2] == ["docs", "+media-insert"]:
            assert self.image_path is not None
            assert cwd_path == self.image_path.parent
            assert args[args.index("--file") + 1] == f".{os.sep}{self.image_path.name}"
            assert args[args.index("--type") + 1] == "image"
            assert args[args.index("--as") + 1] == "bot"
            payload = {
                "ok": True,
                "data": {
                    "document_id": "doc_token",
                    "block_id": "block_image",
                    "file_token": "file_image",
                    "type": "image",
                },
            }
            return CommandResult(
                command=["lark-cli", *args],
                returncode=0,
                stdout=json.dumps(payload, ensure_ascii=False),
                stderr="",
                duration_ms=9,
                parsed_json=payload,
            )
        raise AssertionError(f"unexpected command: {args}")


def test_create_doc_writes_markdown_through_file() -> None:
    markdown = "# Title\n\n正文内容"
    runner = RecordingRunner(markdown)
    executor = ToolExecutor(runner)  # type: ignore[arg-type]

    payload, record = executor.execute("create_doc", {"title": "Title", "markdown": markdown})

    assert payload["document"]["doc_url"] == "https://www.feishu.cn/docx/doc_token"
    assert record.ok is True
    assert runner.calls[0][0][:2] == ["docs", "+create"]
    assert runner.calls[0][0][runner.calls[0][0].index("--as") + 1] == "bot"


def test_create_doc_inserts_media_files(tmp_path: Path) -> None:
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"fake png")
    markdown = "# Title\n\n正文内容"
    runner = RecordingRunner(markdown, image_path=image_path)
    executor = ToolExecutor(runner)  # type: ignore[arg-type]

    payload, _ = executor.execute(
        "create_doc",
        {
            "title": "Title",
            "markdown": markdown,
            "media_files": [{"path": str(image_path), "caption": "Figure 1"}],
        },
    )

    assert len(runner.calls) == 2
    assert runner.calls[1][0][:2] == ["docs", "+media-insert"]
    assert payload["media"][0]["file_token"] == "file_image"
    assert payload["media"][0]["block_id"] == "block_image"
