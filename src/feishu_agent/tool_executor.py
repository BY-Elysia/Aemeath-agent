from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import dataclass
from typing import Any

from .cli_runner import CliRunner, CommandResult
from .errors import ToolExecutionError


@dataclass
class ToolExecutionRecord:
    tool_name: str
    command: list[str]
    stdout: str
    stderr: str
    duration_ms: int
    ok: bool
    error_category: str | None = None


IMAGE_EXTENSIONS = {".apng", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}


class ToolExecutor:
    def __init__(self, runner: CliRunner) -> None:
        self._runner = runner

    def execute(self, tool_name: str, args: dict[str, Any]) -> tuple[dict[str, Any], ToolExecutionRecord]:
        if tool_name == "search_user":
            result = self._runner.run(
                [
                    "contact",
                    "+search-user",
                    "--query",
                    str(args["name"]),
                    "--as",
                    "user",
                    "--format",
                    "json",
                ]
            )
            return self._finalize(tool_name, result, self._normalize_search_user)
        if tool_name == "send_dm":
            result = self._runner.run(
                [
                    "im",
                    "+messages-send",
                    "--user-id",
                    str(args["user_open_id"]),
                    "--text",
                    str(args["text"]),
                    "--as",
                    "bot",
                ]
            )
            return self._finalize(tool_name, result, self._normalize_send_dm)
        if tool_name == "list_agenda":
            date = str(args["date"])
            result = self._runner.run(
                [
                    "calendar",
                    "+agenda",
                    "--start",
                    date,
                    "--end",
                    date,
                    "--as",
                    "user",
                    "--format",
                    "json",
                ]
            )
            return self._finalize(tool_name, result, self._normalize_list_agenda)
        if tool_name == "create_doc":
            return self._execute_create_doc(args)
        if tool_name == "search_messages":
            result = self._runner.run(
                [
                    "im",
                    "+messages-search",
                    "--query",
                    str(args["query"]),
                    "--as",
                    "user",
                    "--format",
                    "json",
                ]
            )
            return self._finalize(tool_name, result, self._normalize_search_messages)
        raise ToolExecutionError("parameter_error", f"unsupported tool: {tool_name}")

    def _execute_create_doc(self, args: dict[str, Any]) -> tuple[dict[str, Any], ToolExecutionRecord]:
        title = str(args["title"])
        markdown = str(args["markdown"])
        send_as = self._normalize_doc_identity(args.get("send_as"))
        media_files = self._normalize_media_files(args.get("media_files") or args.get("mediaFiles") or [])

        with TemporaryDirectory(prefix="feishu-agent-doc-") as temp_dir:
            markdown_path = Path(temp_dir) / "body.md"
            markdown_path.write_text(markdown, encoding="utf-8")
            result = self._runner.run(
                [
                    "docs",
                    "+create",
                    "--title",
                    title,
                    "--markdown",
                    "@body.md",
                    "--as",
                    send_as,
                ],
                cwd=temp_dir,
            )
            payload, record = self._finalize("create_doc", result, self._normalize_create_doc)

        if media_files:
            doc = self._extract_doc_locator(payload)
            inserted_media = self._insert_media_files(doc, media_files, send_as)
            payload["media"] = inserted_media
            record.stdout = json.dumps(payload, ensure_ascii=False)
        return payload, record

    def _finalize(
        self,
        tool_name: str,
        result: CommandResult,
        parser,
    ) -> tuple[dict[str, Any], ToolExecutionRecord]:
        record = ToolExecutionRecord(
            tool_name=tool_name,
            command=result.command,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=result.duration_ms,
            ok=result.returncode == 0,
        )
        parsed = result.parsed_json
        if result.returncode != 0:
            error = self._map_error(parsed, result)
            record.error_category = error.category
            raise error
        payload = parser(parsed if isinstance(parsed, (dict, list)) else result.stdout)
        return payload, record

    def _map_error(self, parsed: dict | list | None, result: CommandResult) -> ToolExecutionError:
        if isinstance(parsed, dict) and "error" in parsed:
            err = parsed.get("error") or {}
            message = str(err.get("message") or "tool execution failed")
            error_type = str(err.get("type") or "api_error")
            code = err.get("code")
            detail = {
                "type": error_type,
                "code": code,
                "hint": err.get("hint"),
                "console_url": err.get("console_url"),
                "identity": parsed.get("identity"),
                "command": result.command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_ms": result.duration_ms,
            }
            lowered = message.lower()
            if error_type in {"validation"}:
                return ToolExecutionError("parameter_error", message, detail)
            if error_type in {"missing_scope", "permission"} or "scope" in lowered:
                return ToolExecutionError("permission_denied", message, detail)
            if "availability" in lowered or str(code) == "230013":
                return ToolExecutionError("bot_availability", message, detail)
            if "not unique" in lowered or "multiple" in lowered:
                return ToolExecutionError("ambiguous_target", message, detail)
            if "need_user_authorization" in lowered:
                return ToolExecutionError("permission_denied", message, detail)
            return ToolExecutionError("tool_error", message, detail)
        if result.returncode != 0:
            return ToolExecutionError(
                "tool_error",
                result.stderr or result.stdout or "tool execution failed",
                {
                    "returncode": result.returncode,
                    "command": result.command,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "duration_ms": result.duration_ms,
                },
            )
        return ToolExecutionError("tool_error", "tool execution failed")

    def _normalize_search_user(self, parsed: dict | str) -> dict[str, Any]:
        raw = parsed if isinstance(parsed, dict) else {}
        data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        users = data.get("users") or []
        matches = []
        for user in users:
            matches.append(
                {
                    "name": user.get("name") or user.get("display_name") or user.get("user_name"),
                    "open_id": user.get("open_id"),
                    "email": user.get("email") or user.get("mail"),
                    "mobile": user.get("mobile") or user.get("phone"),
                    "department": user.get("department_name") or user.get("department"),
                    "enterprise_email": user.get("enterprise_email"),
                }
            )
        return {
            "matches": matches,
            "has_more": bool(data.get("has_more")),
            "page_token": data.get("page_token") or "",
        }

    def _normalize_send_dm(self, parsed: dict | str) -> dict[str, Any]:
        data = parsed if isinstance(parsed, dict) else {}
        payload = data.get("data") or data
        return {
            "message_id": payload.get("message_id"),
            "chat_id": payload.get("chat_id"),
            "create_time": payload.get("create_time"),
        }

    def _normalize_list_agenda(self, parsed: dict | list | str) -> dict[str, Any]:
        if isinstance(parsed, dict):
            raw_items = parsed.get("data")
            items = raw_items if isinstance(raw_items, list) else []
        else:
            items = parsed if isinstance(parsed, list) else []
        events = []
        for item in items:
            events.append(
                {
                    "event_id": item.get("event_id"),
                    "summary": item.get("summary") or "(untitled)",
                    "start_time": item.get("start_time"),
                    "end_time": item.get("end_time"),
                    "free_busy_status": item.get("free_busy_status"),
                    "self_rsvp_status": item.get("self_rsvp_status"),
                }
            )
        return {"events": events, "total": len(events)}

    def _normalize_create_doc(self, parsed: dict | str) -> dict[str, Any]:
        raw = parsed if isinstance(parsed, dict) else {"raw": parsed}
        data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        return {"document": data}

    @staticmethod
    def _normalize_doc_identity(value: Any) -> str:
        # Docs/media operations are intentionally bot-backed: local user OAuth tokens expire,
        # while bot-created docs are still granted to the current CLI user by lark-cli.
        identity = str(value or "bot").strip().lower()
        return identity if identity == "bot" else "bot"

    def _normalize_media_files(self, raw_media_files: Any) -> list[dict[str, Any]]:
        if not raw_media_files:
            return []
        if isinstance(raw_media_files, (str, Path)):
            raw_items = [raw_media_files]
        elif isinstance(raw_media_files, list):
            raw_items = raw_media_files
        else:
            raise ToolExecutionError("parameter_error", "media_files must be a list")

        media_files: list[dict[str, Any]] = []
        for item in raw_items:
            if isinstance(item, (str, Path)):
                raw_path = str(item)
                raw_type = ""
                caption = ""
                align = ""
            elif isinstance(item, dict):
                raw_path = str(item.get("path") or item.get("file") or "").strip()
                raw_type = str(item.get("type") or "").strip().lower()
                caption = str(item.get("caption") or item.get("alt") or "").strip()
                align = str(item.get("align") or "").strip().lower()
            else:
                raise ToolExecutionError("parameter_error", "media_files items must be paths or objects")

            if not raw_path:
                raise ToolExecutionError("parameter_error", "media file path is required")
            path = Path(raw_path).expanduser().resolve()
            if not path.is_file():
                raise ToolExecutionError("parameter_error", f"media file does not exist: {raw_path}")

            media_type = raw_type or ("image" if path.suffix.lower() in IMAGE_EXTENSIONS else "file")
            if media_type not in {"image", "file"}:
                raise ToolExecutionError("parameter_error", "media file type must be image or file")
            if align and align not in {"left", "center", "right"}:
                raise ToolExecutionError("parameter_error", "media file align must be left, center, or right")

            media_files.append(
                {
                    "path": path,
                    "type": media_type,
                    "caption": caption,
                    "align": align or ("center" if media_type == "image" else ""),
                }
            )
        return media_files

    @staticmethod
    def _extract_doc_locator(payload: dict[str, Any]) -> str:
        document = payload.get("document") if isinstance(payload.get("document"), dict) else {}
        for key in ("doc_url", "url", "document_url", "doc_id", "document_id", "token"):
            value = str(document.get(key) or "").strip()
            if value:
                return value
        raise ToolExecutionError("tool_error", "created document response did not include a document URL or ID")

    def _insert_media_files(self, doc: str, media_files: list[dict[str, Any]], send_as: str) -> list[dict[str, Any]]:
        inserted: list[dict[str, Any]] = []
        for media in media_files:
            path = media["path"]
            relative_file = f".{os.sep}{path.name}"
            command = [
                "docs",
                "+media-insert",
                "--doc",
                doc,
                "--file",
                relative_file,
                "--type",
                media["type"],
                "--as",
                send_as,
            ]
            if media["caption"]:
                command.extend(["--caption", media["caption"]])
            if media["type"] == "image" and media["align"]:
                command.extend(["--align", media["align"]])
            result = self._runner.run(command, cwd=path.parent)
            if result.returncode != 0:
                raise self._map_error(result.parsed_json, result)

            raw = result.parsed_json if isinstance(result.parsed_json, dict) else {}
            data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
            inserted.append(
                {
                    "path": str(path),
                    "type": media["type"],
                    "caption": media["caption"],
                    "align": media["align"],
                    "block_id": data.get("block_id"),
                    "file_token": data.get("file_token"),
                    "document_id": data.get("document_id"),
                }
            )
        return inserted

    def _normalize_search_messages(self, parsed: dict | str) -> dict[str, Any]:
        raw = parsed if isinstance(parsed, dict) else {}
        data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        return {
            "messages": data.get("messages") or [],
            "total": data.get("total") or 0,
            "has_more": bool(data.get("has_more")),
            "page_token": data.get("page_token") or "",
        }


def summarize_pending_action(tool_name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if tool_name == "send_dm":
        return (
            "待确认：向指定飞书用户发送私聊消息。",
            {
                "user_open_id": args["user_open_id"],
                "text": args["text"],
                "send_as": "bot",
            },
        )
    if tool_name == "create_doc":
        return (
            "待确认：创建一篇新的飞书文档。",
            {
                "title": args["title"],
                "markdown_preview": str(args["markdown"])[:120],
                "media_files": args.get("media_files") or [],
                "send_as": "bot",
            },
        )
    if tool_name == "read_paper_url_to_feishu_doc":
        return (
            "待确认：阅读论文网址并创建飞书文档。",
            {
                "title": str(args.get("title") or "").strip(),
                "paper_url": str(args.get("paper_url") or "").strip(),
                "focus": str(args.get("focus") or "").strip(),
                "max_pages": args.get("max_pages") or 8,
                "send_as": "bot",
            },
        )
    return (
        f"待确认：执行 {tool_name}",
        args,
    )
