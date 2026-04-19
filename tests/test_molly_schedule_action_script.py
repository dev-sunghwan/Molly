import subprocess
import sys


def test_molly_schedule_action_view_help():
    result = subprocess.run(
        [sys.executable, "scripts/molly_schedule_action.py", "view", "--help"],
        cwd="/home/sunghwan/projects/Molly",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--scope" in result.stdout
    assert "--actor-user-id" in result.stdout
    assert "--actor-name" in result.stdout


def test_molly_schedule_action_search_help():
    result = subprocess.run(
        [sys.executable, "scripts/molly_schedule_action.py", "search", "--help"],
        cwd="/home/sunghwan/projects/Molly",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--query" in result.stdout
    assert "--actor-name" in result.stdout


def test_molly_schedule_action_create_help_shows_recurrence_options():
    result = subprocess.run(
        [sys.executable, "scripts/molly_schedule_action.py", "create", "--help"],
        cwd="/home/sunghwan/projects/Molly",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--recurrence" in result.stdout
    assert "--weekly-day" in result.stdout
    assert "--actor-user-id" in result.stdout
    assert "--actor-name" in result.stdout


def test_molly_schedule_action_gmail_confirm_help():
    result = subprocess.run(
        [sys.executable, "scripts/molly_schedule_action.py", "gmail-confirm", "--help"],
        cwd="/home/sunghwan/projects/Molly",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--candidate-id" in result.stdout
    assert "--actor-user-id" in result.stdout
    assert "--actor-name" in result.stdout
