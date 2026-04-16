import json
import subprocess
from pathlib import Path

def test_molly_create_event_script_executes():
    script_path = Path("scripts/molly_create_event.py")
    completed = subprocess.run(
        [
            str(Path(".venv/bin/python")),
            str(script_path),
            "--calendar",
            "younha",
            "--title",
            "Tennis",
            "--date",
            "2026-04-16",
            "--start",
            "17:00",
            "--end",
            "18:00",
            "--raw-input",
            "내일 오후 5시에 윤하 테니스 넣어줘",
        ],
        capture_output=True,
        check=True,
        text=True,
        cwd=Path.cwd(),
    )

    payload = json.loads(completed.stdout)

    assert payload["success"] is True
    assert payload["action"] == "create_event"
    assert "Added to YounHa" in payload["message"]
