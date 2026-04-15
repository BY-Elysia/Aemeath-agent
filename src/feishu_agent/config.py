from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .skills import DEFAULT_ENABLED_SKILLS


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class AppConfig:
    ark_api_key: str
    ark_base_url: str
    ark_model: str
    lark_cli_bin: str
    app_db_path: Path
    command_timeout_seconds: int
    max_history_messages: int
    max_tool_round_trips: int
    feishu_agent_base_url: str
    auto_reply_p2p_only: bool
    group_reply_mode: str
    bot_mention_ids: tuple[str, ...]
    bot_mention_names: tuple[str, ...]
    agent_persona: str = "aemeath"
    enabled_skills: tuple[str, ...] = DEFAULT_ENABLED_SKILLS

    @classmethod
    def from_env(cls) -> "AppConfig":
        db_path = Path(os.getenv("APP_DB_PATH", "./data/app.db")).expanduser().resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return cls(
            ark_api_key=os.getenv("ARK_API_KEY", ""),
            ark_base_url=os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
            ark_model=os.getenv("ARK_MODEL", ""),
            lark_cli_bin=os.getenv("LARK_CLI_BIN", "lark-cli"),
            app_db_path=db_path,
            command_timeout_seconds=int(os.getenv("COMMAND_TIMEOUT_SECONDS", "30")),
            max_history_messages=int(os.getenv("MAX_HISTORY_MESSAGES", "20")),
            max_tool_round_trips=int(os.getenv("MAX_TOOL_ROUND_TRIPS", "6")),
            feishu_agent_base_url=os.getenv("FEISHU_AGENT_BASE_URL", "http://127.0.0.1:8000"),
            auto_reply_p2p_only=os.getenv("AUTO_REPLY_P2P_ONLY", "true").strip().lower()
            not in {"0", "false", "no", "off"},
            group_reply_mode=cls._resolve_group_reply_mode(),
            bot_mention_ids=cls._split_csv_env("BOT_MENTION_IDS"),
            bot_mention_names=cls._split_csv_env("BOT_MENTION_NAMES"),
            agent_persona=os.getenv("AGENT_PERSONA", "aemeath").strip().lower() or "aemeath",
            enabled_skills=cls._resolve_enabled_skills(),
        )

    @staticmethod
    def _resolve_group_reply_mode() -> str:
        mode = os.getenv("GROUP_REPLY_MODE", "").strip().lower()
        if mode:
            return mode
        legacy_p2p_only = os.getenv("AUTO_REPLY_P2P_ONLY", "true").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        return "off" if legacy_p2p_only else "all"

    @staticmethod
    def _split_csv_env(name: str) -> tuple[str, ...]:
        value = os.getenv(name, "").strip()
        if not value:
            return ()
        return tuple(item.strip() for item in value.split(",") if item.strip())

    @staticmethod
    def _resolve_enabled_skills() -> tuple[str, ...]:
        value = os.getenv("ENABLED_SKILLS", "").strip()
        if not value:
            return DEFAULT_ENABLED_SKILLS
        return tuple(item.strip() for item in value.split(",") if item.strip())

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.ark_api_key:
            errors.append("ARK_API_KEY is not set")
        if not self.ark_model:
            errors.append("ARK_MODEL is not set")
        if not self.ark_base_url:
            errors.append("ARK_BASE_URL is not set")
        if not self.lark_cli_bin:
            errors.append("LARK_CLI_BIN is not set")
        if not self.feishu_agent_base_url:
            errors.append("FEISHU_AGENT_BASE_URL is not set")
        if not self.agent_persona:
            errors.append("AGENT_PERSONA is not set")
        if not self.enabled_skills:
            errors.append("ENABLED_SKILLS must not be empty")
        if self.group_reply_mode not in {"off", "all", "mention"}:
            errors.append("GROUP_REPLY_MODE must be one of: off, all, mention")
        if self.command_timeout_seconds <= 0:
            errors.append("COMMAND_TIMEOUT_SECONDS must be positive")
        if self.max_history_messages <= 0:
            errors.append("MAX_HISTORY_MESSAGES must be positive")
        if self.max_tool_round_trips <= 0:
            errors.append("MAX_TOOL_ROUND_TRIPS must be positive")
        return errors
