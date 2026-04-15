from __future__ import annotations

from feishu_agent.shell import ShellClient


class FakeHarness:
    def whoami(self):
        return type("Identity", (), {"persona": "aemeath", "model": "ep-test", "skills": ("conversation",)})()


def test_unknown_command_returns_false(capsys) -> None:
    client = ShellClient(FakeHarness(), "s1")
    should_exit = client._handle_command("/unknown")
    captured = capsys.readouterr()
    assert should_exit is False
    assert "未知命令" in captured.out


def test_session_command_switches_session(capsys) -> None:
    client = ShellClient(FakeHarness(), "s1")
    should_exit = client._handle_command("/session demo-2")
    captured = capsys.readouterr()
    assert should_exit is False
    assert "demo-2" in captured.out
