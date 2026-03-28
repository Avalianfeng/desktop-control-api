from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from recorder.recorder import UIARecorder


def _default_out_path() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(Path("updates") / "recorder" / f"recorder_{ts}.jsonl")


def _state_path() -> Path:
    return Path("updates") / "recorder" / "recorder.state.json"


def _stop_signal_path() -> Path:
    return Path("updates") / "recorder" / "recorder.stop"


def _write_state(out_path: str) -> None:
    state = {
        "pid": os.getpid(),
        "out_path": out_path,
        "started_at": datetime.now().isoformat(),
        "status": "running",
    }
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _clear_state() -> None:
    for p in (_state_path(), _stop_signal_path()):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


def cmd_start(out: Optional[str], window_title: Optional[str]) -> int:
    out_path = out or _default_out_path()
    stop_path = _stop_signal_path()
    if stop_path.exists():
        stop_path.unlink()
    _write_state(out_path)

    print("[Recorder] Listening UIA events...")
    print("[Recorder] Press Ctrl+C to stop")
    print(f"[Recorder] Output: {out_path}")

    recorder = UIARecorder(out_path, window_title=window_title)
    try:
        count = recorder.run_until_interrupt(stop_file=str(stop_path))
    except Exception as exc:
        _clear_state()
        print(f"[Recorder] failed to start: {exc}")
        return 2
    _clear_state()
    print(f"[Recorder] {count} events captured")
    event_counts = recorder.event_counts
    if event_counts:
        top_items = sorted(event_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
        summary = ", ".join(f"{name}={cnt}" for name, cnt in top_items)
        print(f"[Recorder] Event distribution: {summary}")
    # v1.8.5: Sanitization drop stats are printed by recorder.stop(); keep CLI concise.
    print(f"[Recorder] Saved to {out_path}")
    return 0


def cmd_stop() -> int:
    state = _state_path()
    if not state.exists():
        print("[Recorder] not running")
        return 1
    sig = _stop_signal_path()
    sig.parent.mkdir(parents=True, exist_ok=True)
    sig.write_text("stop", encoding="utf-8")
    print("[Recorder] stop signal sent")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Desktop Control Dev Recorder (MVP)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="Start recorder in foreground")
    p_start.add_argument("--out", default=None, help="Output JSONL path")
    p_start.add_argument(
        "--window-title",
        default=None,
        help="Optional window title (used as subscription root when found; also used as output filter)",
    )

    sub.add_parser("stop", help="Request recorder stop")
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.cmd == "start":
        return cmd_start(args.out, args.window_title)
    if args.cmd == "stop":
        return cmd_stop()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

