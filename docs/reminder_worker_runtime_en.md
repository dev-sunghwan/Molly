# Reminder Worker Runtime

## Recommended Runtime

Molly's reminders, daily summaries, and tomorrow previews are now handled by:

- `scripts/run_reminder_worker.py`

Because this worker has been separated from `bot.py`, it should run as its own long-lived process in real operation.

The recommended approach is:

- `systemd --user`

## Why `systemd --user` Is Preferred

- it manages the worker as a user-level service
- it is easy to enable automatic startup
- it can restart the worker if the process exits
- it makes status, restart, and log inspection straightforward

## File Added In The Repo

- `deploy/systemd/molly-reminder-worker.service`

This service runs:

```bash
/home/sunghwan/projects/Molly/.venv/bin/python /home/sunghwan/projects/Molly/scripts/run_reminder_worker.py
```

## Installation Shape

The normal flow is:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/molly-reminder-worker.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now molly-reminder-worker.service
```

## Common Commands

Check status:

```bash
systemctl --user status molly-reminder-worker.service
```

Restart:

```bash
systemctl --user restart molly-reminder-worker.service
```

Stop:

```bash
systemctl --user stop molly-reminder-worker.service
```

Show logs:

```bash
journalctl --user -u molly-reminder-worker.service -n 100 --no-pager
```

## Alternative

For a temporary setup, `tmux` is also acceptable:

```bash
tmux new -s molly-reminder
./.venv/bin/python scripts/run_reminder_worker.py
```

But for ongoing operation, `systemd --user` is the cleaner choice.
