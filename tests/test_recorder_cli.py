from __future__ import annotations

from pathlib import Path

import recorder.cli as cli


def test_cmd_stop_not_running(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = cli.cmd_stop()
    out = capsys.readouterr().out
    assert rc == 1
    assert "not running" in out


def test_cmd_stop_writes_signal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state = tmp_path / "updates" / "recorder" / "recorder.state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("{}", encoding="utf-8")
    rc = cli.cmd_stop()
    assert rc == 0
    assert (tmp_path / "updates" / "recorder" / "recorder.stop").exists()


def test_cmd_start_runs_and_clears_state(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    class _StubRecorder:
        def __init__(self, out_path: str, *, window_title=None):
            self.out_path = out_path
            self.window_title = window_title
            self.event_counts = {"selection": 5, "invoke": 2}

        def run_until_interrupt(self, *, stop_file=None, poll_interval_s=0.2):  # noqa: ARG002
            return 7

    monkeypatch.setattr(cli, "UIARecorder", _StubRecorder)
    rc = cli.cmd_start(out=str(tmp_path / "updates" / "recorder" / "x.jsonl"), window_title="Notepad")
    out = capsys.readouterr().out
    assert rc == 0
    assert "7 events captured" in out
    assert "Event distribution" in out
    assert not (tmp_path / "updates" / "recorder" / "recorder.state.json").exists()


def test_cmd_start_failure_returns_nonzero_and_clears_state(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    class _StubRecorderFail:
        def __init__(self, out_path: str, *, window_title=None):  # noqa: ARG002
            self.out_path = out_path

        def run_until_interrupt(self, *, stop_file=None, poll_interval_s=0.2):  # noqa: ARG002
            raise RuntimeError("bridge failed")

    monkeypatch.setattr(cli, "UIARecorder", _StubRecorderFail)
    rc = cli.cmd_start(out=str(tmp_path / "updates" / "recorder" / "x.jsonl"), window_title=None)
    out = capsys.readouterr().out
    assert rc == 2
    assert "failed to start" in out
    assert not (tmp_path / "updates" / "recorder" / "recorder.state.json").exists()

