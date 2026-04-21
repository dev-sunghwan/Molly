import subprocess
import sys


def test_molly_gmail_action_help():
    completed = subprocess.run(
        [sys.executable, "scripts/molly_gmail_action.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "process" in completed.stdout
    assert "confirm" in completed.stdout
    assert "notify-pending" in completed.stdout
