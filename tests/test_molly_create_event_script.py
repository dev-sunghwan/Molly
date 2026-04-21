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
    assert (
        "Added to YounHa" in payload["message"]
        or "Already exists in YounHa" in payload["message"]
    )


def test_molly_create_event_script_supports_weekly_recurrence():
    script_path = Path("scripts/molly_create_event.py")
    completed = subprocess.run(
        [
            str(Path(".venv/bin/python")),
            str(script_path),
            "--calendar",
            "younha",
            "--title",
            "Alpha-Math",
            "--date",
            "2026-04-17",
            "--start",
            "17:00",
            "--end",
            "18:00",
            "--weekly-day",
            "FR",
            "--raw-input",
            "윤하 오후 5시-6시 Alpha-Math 일정 넣어줘. 매주 금요일 반복이야.",
        ],
        capture_output=True,
        check=True,
        text=True,
        cwd=Path.cwd(),
    )

    payload = json.loads(completed.stdout)

    assert payload["success"] is True
    assert "(weekly recurring)" in payload["message"]


def test_molly_create_event_help_shows_actor_user_id():
    script_path = Path("scripts/molly_create_event.py")
    completed = subprocess.run(
        [
            str(Path(".venv/bin/python")),
            str(script_path),
            "--help",
        ],
        capture_output=True,
        check=True,
        text=True,
        cwd=Path.cwd(),
    )

    assert "--actor-user-id" in completed.stdout
