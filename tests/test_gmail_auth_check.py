from pathlib import Path


def test_gmail_auth_check_script_exists():
    script_path = Path("scripts/gmail_auth_check.py")
    assert script_path.exists()
