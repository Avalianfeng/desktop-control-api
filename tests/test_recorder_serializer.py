from __future__ import annotations

import json

from recorder.serializer import JsonlSerializer


def test_jsonl_serializer_writes_one_line(tmp_path):
    out = tmp_path / "recorder.jsonl"
    s = JsonlSerializer(str(out))
    s.append({"event": "invoke", "control": {"name": "按钮"}})
    s.close()

    content = out.read_text(encoding="utf-8").strip()
    obj = json.loads(content)
    assert obj["event"] == "invoke"
    assert obj["control"]["name"] == "按钮"

