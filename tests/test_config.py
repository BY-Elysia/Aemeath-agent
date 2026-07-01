from __future__ import annotations

import feishu_agent.config as config_module
from feishu_agent.config import AppConfig, resolve_lark_cli_bin


def test_resolve_lark_cli_bin_finds_windows_npm_shim(tmp_path, monkeypatch) -> None:
    appdata = tmp_path / "Roaming"
    npm_dir = appdata / "npm"
    npm_dir.mkdir(parents=True)
    shim = npm_dir / "lark-cli.cmd"
    shim.write_text("@echo off\n", encoding="utf-8")

    monkeypatch.setattr(config_module.os, "name", "nt")
    monkeypatch.setattr(config_module.shutil, "which", lambda _name: None)
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.delenv("USERPROFILE", raising=False)

    assert resolve_lark_cli_bin("lark-cli") == str(shim)


def test_enabled_capabilities_prefers_new_env_name(monkeypatch) -> None:
    monkeypatch.setenv("ENABLED_SKILLS", "conversation")
    monkeypatch.setenv("ENABLED_CAPABILITIES", "conversation,feishu_contact")

    assert AppConfig._resolve_enabled_capabilities() == ("conversation", "feishu_contact")


def test_enabled_capabilities_accepts_legacy_enabled_skills(monkeypatch) -> None:
    monkeypatch.delenv("ENABLED_CAPABILITIES", raising=False)
    monkeypatch.setenv("ENABLED_SKILLS", "conversation")

    assert AppConfig._resolve_enabled_capabilities() == ("conversation",)
