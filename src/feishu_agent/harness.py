from __future__ import annotations

import re
from dataclasses import dataclass

from .ark_client import ArkClient
from .cli_runner import CliRunner
from .config import AppConfig
from .errors import PendingActionError, ToolExecutionError
from .persona import resolve_persona_prompt
from .prompting import build_policy_prompt, build_prompt
from .schemas import ChatResponse, ConfirmActionResponse, HealthResponse, PendingActionView
from .skills import load_skills
from .skills.base import Skill, SkillContext, ToolSpec
from .store import SessionStore
from .tool_executor import ToolExecutor, summarize_pending_action
from .tool_registry import index_tools, responses_tools


@dataclass(frozen=True)
class AgentIdentity:
    persona: str
    model: str
    skills: tuple[str, ...]


class AgentHarness:
    def __init__(
        self,
        *,
        config: AppConfig,
        store: SessionStore,
        ark_client: ArkClient,
        tool_executor: ToolExecutor,
        skills: list[Skill] | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._ark_client = ark_client
        self._tool_executor = tool_executor
        self._skills = skills or load_skills(config.enabled_skills, tool_executor)
        self._tools_by_name = index_tools(self._collect_tools())
        self._skills_by_tool = self._index_skill_owners()
        self._persona_prompt = resolve_persona_prompt(config.agent_persona)
        self._policy_prompt = build_policy_prompt()

    def handle_message(self, session_id: str, message: str, source: str = "api") -> ChatResponse:
        self._store.ensure_session(session_id)
        history = self._store.get_messages(session_id, self._config.max_history_messages)
        self._store.append_message(session_id, "user", message, metadata={"source": source})
        history = history + [{"role": "user", "content": message, "metadata": {"source": source}}]
        tool_events: list[dict] = []

        for _ in range(self._config.max_tool_round_trips):
            prompt = build_prompt(
                persona_prompt=self._persona_prompt,
                policy_prompt=self._policy_prompt,
                skill_guidance=[skill.get_guidance() for skill in self._skills if skill.get_guidance()],
                history=history[:-1],
                latest_user_message=message,
                tool_events=tool_events,
                source=source,
            )
            model_response = self._ark_client.create_response(prompt, responses_tools(self._tools_by_name.values()))

            if model_response.function_calls:
                for call in model_response.function_calls:
                    tool = self._tools_by_name.get(call.name)
                    if tool is None:
                        return self._message_response(
                            session_id,
                            f"模型请求了未注册工具：{call.name}",
                            status="error",
                        )

                    if tool.requires_confirmation:
                        return self._build_pending_action(
                            session_id=session_id,
                            tool_name=call.name,
                            args=call.arguments,
                        )

                    try:
                        result, record = self._execute_tool(
                            session_id=session_id,
                            action_id=None,
                            tool_name=call.name,
                            args=call.arguments,
                            source=source,
                        )
                    except ToolExecutionError as exc:
                        return self._message_response(
                            session_id,
                            self._format_tool_error(exc),
                            status="error",
                        )

                    tool_events.append(
                        {
                            "tool": call.name,
                            "arguments": call.arguments,
                            "result": result,
                        }
                    )
                    if call.name == "search_user":
                        fallback = self._maybe_build_send_dm_from_search_result(
                            session_id=session_id,
                            original_message=message,
                            search_result=result,
                        )
                        if fallback is not None:
                            return fallback
                continue

            text = model_response.text or "未获得模型输出。"
            return self._message_response(session_id, text)

        return self._message_response(
            session_id,
            "工具调用轮次超过限制，未能完成本次请求。",
            status="error",
        )

    def confirm_action(self, action_id: str, confirm: bool) -> ConfirmActionResponse:
        pending = self._store.get_pending_action(action_id)
        if pending is None:
            raise PendingActionError(f"pending action not found: {action_id}")
        if pending["status"] != "pending":
            raise PendingActionError(f"pending action is already {pending['status']}")

        if not confirm:
            self._store.update_pending_action(action_id, "cancelled")
            cancel_message = "已取消待执行动作。"
            self._store.append_message(
                pending["session_id"],
                "assistant",
                cancel_message,
                metadata={"action_id": action_id, "status": "cancelled"},
            )
            return ConfirmActionResponse(
                status="cancelled",
                action_id=action_id,
                message=cancel_message,
                result=None,
            )

        try:
            result, _ = self._execute_tool(
                session_id=pending["session_id"],
                action_id=action_id,
                tool_name=pending["tool_name"],
                args=pending["args"],
                source="confirm",
            )
        except ToolExecutionError as exc:
            self._store.update_pending_action(
                action_id,
                "failed",
                error={"category": exc.category, "message": exc.message, "detail": exc.detail},
            )
            return ConfirmActionResponse(
                status="error",
                action_id=action_id,
                message=self._format_tool_error(exc),
                result=None,
            )

        self._store.update_pending_action(action_id, "executed", result=result)
        success_message = self._format_success_message(pending["tool_name"], result)
        self._store.append_message(
            pending["session_id"],
            "assistant",
            success_message,
            metadata={"action_id": action_id, "status": "executed", "result": result},
        )
        return ConfirmActionResponse(
            status="executed",
            action_id=action_id,
            message=success_message,
            result=result,
        )

    def healthcheck(self) -> HealthResponse:
        errors = self._config.validate()
        return HealthResponse(
            ok=not errors,
            config_errors=errors,
            lark_cli_bin=self._config.lark_cli_bin,
            db_path=str(self._config.app_db_path),
        )

    def whoami(self) -> AgentIdentity:
        return AgentIdentity(
            persona=self._config.agent_persona,
            model=self._config.ark_model,
            skills=tuple(skill.name for skill in self._skills),
        )

    def list_skills(self) -> list[dict[str, str]]:
        return [{"name": skill.name, "description": skill.description} for skill in self._skills]

    def get_session_history(self, session_id: str, limit: int | None = None) -> list[dict]:
        capped = limit or self._config.max_history_messages
        return self._store.get_messages(session_id, capped)

    def get_pending_action_for_session(self, session_id: str) -> dict | None:
        return self._store.get_latest_pending_action_for_session(session_id)

    def _collect_tools(self) -> list[ToolSpec]:
        tools: list[ToolSpec] = []
        for skill in self._skills:
            tools.extend(skill.get_tools())
        return tools

    def _index_skill_owners(self) -> dict[str, Skill]:
        owners: dict[str, Skill] = {}
        for skill in self._skills:
            for tool in skill.get_tools():
                owners[tool.name] = skill
        return owners

    def _execute_tool(
        self,
        *,
        session_id: str,
        action_id: str | None,
        tool_name: str,
        args: dict,
        source: str,
    ):
        skill = self._skills_by_tool.get(tool_name)
        if skill is None:
            raise ToolExecutionError("parameter_error", f"unsupported tool: {tool_name}")
        try:
            result, record = skill.execute(tool_name, args, SkillContext(session_id=session_id, source=source))
        except ToolExecutionError as exc:
            detail = exc.detail or {}
            self._store.log_tool_call(
                session_id=session_id,
                action_id=action_id,
                tool_name=tool_name,
                command=detail.get("command") or [],
                stdout_text=detail.get("stdout") or "",
                stderr_text=detail.get("stderr") or str(exc),
                ok=False,
                error_category=exc.category,
                duration_ms=detail.get("duration_ms") or 0,
            )
            raise
        self._store.log_tool_call(
            session_id=session_id,
            action_id=action_id,
            tool_name=tool_name,
            command=record.command,
            stdout_text=record.stdout,
            stderr_text=record.stderr,
            ok=True,
            error_category=None,
            duration_ms=record.duration_ms,
        )
        return result, record

    def _message_response(self, session_id: str, text: str, status: str = "message") -> ChatResponse:
        self._store.append_message(session_id, "assistant", text)
        return ChatResponse(status=status, session_id=session_id, message=text)

    def _build_pending_action(self, *, session_id: str, tool_name: str, args: dict) -> ChatResponse:
        summary, args_preview = summarize_pending_action(tool_name, args)
        pending = self._store.create_pending_action(
            session_id=session_id,
            tool_name=tool_name,
            args=args,
            summary=summary,
            args_preview=args_preview,
        )
        self._store.append_message(
            session_id,
            "assistant",
            summary,
            metadata={"pending_action_id": pending["action_id"], "tool_name": tool_name},
        )
        return ChatResponse(
            status="pending_action",
            session_id=session_id,
            message=summary,
            pending_action=PendingActionView(
                action_id=pending["action_id"],
                tool_name=tool_name,
                summary=summary,
                args_preview=args_preview,
            ),
        )

    def _maybe_build_send_dm_from_search_result(
        self,
        *,
        session_id: str,
        original_message: str,
        search_result: dict,
    ) -> ChatResponse | None:
        if "send_dm" not in self._tools_by_name:
            return None
        if not self._looks_like_send_dm_request(original_message):
            return None

        matches = search_result.get("matches") or []
        if len(matches) != 1:
            return None

        message_text = self._extract_dm_text(original_message, matches[0].get("name") or "")
        if not message_text:
            return None
        if not self._should_auto_promote_send_dm(original_message, message_text):
            return None

        args = {
            "user_open_id": matches[0]["open_id"],
            "text": message_text,
            "send_as": "bot",
        }
        return self._build_pending_action(session_id=session_id, tool_name="send_dm", args=args)

    def _looks_like_send_dm_request(self, text: str) -> bool:
        return ("发" in text or "发送" in text) and ("给" in text or "私聊" in text)

    def _extract_dm_text(self, text: str, matched_name: str) -> str | None:
        escaped_name = re.escape(matched_name) if matched_name else None
        patterns = []
        if escaped_name:
            patterns.extend(
                [
                    rf"给\s*{escaped_name}\s*发(?:消息|信息)\s*[:：]?\s*(.+)$",
                    rf"给\s*{escaped_name}\s*发送?\s*(.+)$",
                    rf"给\s*{escaped_name}\s*发\s*(.+)$",
                    rf"发消息给\s*{escaped_name}\s*[:：]?\s*(.+)$",
                    rf"发给\s*{escaped_name}\s*[:：]?\s*(.+)$",
                ]
            )
        patterns.extend(
            [
                r"给\s*open_id\s*为\s*[A-Za-z0-9_]+\s*的用户\s*发送?\s*(.+)$",
                r"给\s*open_id\s*为\s*[A-Za-z0-9_]+\s*的用户\s*发\s*(.+)$",
            ]
        )

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                candidate = match.group(1).strip()
                if candidate:
                    return candidate
        return None

    def _should_auto_promote_send_dm(self, original_message: str, message_text: str) -> bool:
        candidate = " ".join(str(message_text).split()).strip()
        if not candidate:
            return False

        quoted_patterns = [
            r"[\"“”'']([^\"“”'']+)[\"“”'']",
            r"内容[是为]\s*[\"“”'']([^\"“”'']+)[\"“”'']",
        ]
        for pattern in quoted_patterns:
            if re.search(pattern, original_message):
                return True

        meta_prefixes = (
            "内容是",
            "内容为",
            "信息是",
            "信息为",
            "消息是",
            "消息为",
        )
        if candidate.startswith(meta_prefixes):
            return False

        meta_phrases = (
            "介绍一下你自己",
            "介绍你自己",
            "自我介绍",
            "帮我介绍",
            "替我介绍",
            "帮我问候",
            "替我问候",
            "帮我回复",
            "替我回复",
            "帮我提醒",
            "替我提醒",
            "帮我通知",
            "替我通知",
            "帮我写",
            "替我写",
            "写一段",
            "生成",
            "总结一下",
            "解释一下",
        )
        if any(phrase in candidate for phrase in meta_phrases):
            return False

        if len(candidate) <= 20 and not any(mark in candidate for mark in ("：", ":", "\n")):
            return True
        return False

    def _format_tool_error(self, exc: ToolExecutionError) -> str:
        if exc.category == "permission_denied":
            return f"权限不足：{exc.message}"
        if exc.category == "bot_availability":
            return f"机器人可用范围不足：{exc.message}"
        if exc.category == "parameter_error":
            return f"参数错误：{exc.message}"
        if exc.category == "ambiguous_target":
            return f"目标不明确：{exc.message}"
        return f"工具执行失败：{exc.message}"

    def _format_success_message(self, tool_name: str, result: dict) -> str:
        if tool_name == "send_dm":
            return f"已发送消息，message_id={result.get('message_id')}。"
        if tool_name == "create_doc":
            return "已创建飞书文档。"
        return f"已执行 {tool_name}。"


def build_harness(
    config: AppConfig,
    *,
    store: SessionStore | None = None,
    runner: CliRunner | None = None,
    tool_executor: ToolExecutor | None = None,
    ark_client: ArkClient | None = None,
    skills: list[Skill] | None = None,
) -> AgentHarness:
    runtime_store = store or SessionStore(config.app_db_path)
    runtime_runner = runner or CliRunner(config.lark_cli_bin, config.command_timeout_seconds)
    runtime_executor = tool_executor or ToolExecutor(runtime_runner)
    runtime_ark_client = ark_client or ArkClient(
        api_key=config.ark_api_key,
        base_url=config.ark_base_url,
        model=config.ark_model,
    )
    return AgentHarness(
        config=config,
        store=runtime_store,
        ark_client=runtime_ark_client,
        tool_executor=runtime_executor,
        skills=skills,
    )
