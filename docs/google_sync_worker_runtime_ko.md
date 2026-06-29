# Google Sync Worker 운영 메모

## 목적

Molly의 local SQLite calendar DB가 source of truth이고, Google Calendar는 비동기 sync target이다. 이 worker는 `google_sync_outbox`에 쌓인 작업을 Telegram/OpenClaw 응답 경로 밖에서 Google Calendar에 반영한다.

현재 production 연결은 보수적으로 `create` 작업만 처리한다. `update`, `delete`, `move`, `delete_series`는 아직 Google에 직접 반영하지 않고 `unsupported` 상태로 남긴다.

## Runtime 방식

저사양 MacBook Pro에서 장시간 상주 프로세스를 하나 더 늘리지 않기 위해 `systemd --user` timer를 사용한다.

- service: `deploy/systemd/molly-google-sync-worker.service`
- timer: `deploy/systemd/molly-google-sync-worker.timer`
- 실행 주기: 부팅 2분 후, 이후 마지막 실행 기준 5분마다
- batch 크기: 한 번에 최대 5개 outbox row

실행 명령:

```bash
/home/sunghwan/projects/Molly/.venv/bin/python /home/sunghwan/projects/Molly/scripts/run_google_sync_worker.py --once --limit 5 --max-attempts 5
```

## 설치

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/molly-google-sync-worker.service ~/.config/systemd/user/
cp deploy/systemd/molly-google-sync-worker.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now molly-google-sync-worker.timer
```

## 상태 확인

```bash
systemctl --user status molly-google-sync-worker.timer --no-pager
systemctl --user status molly-google-sync-worker.service --no-pager
journalctl --user -u molly-google-sync-worker.service -n 80 --no-pager
./.venv/bin/python scripts/molly_admin.py sync --limit 20
./.venv/bin/python scripts/molly_admin.py summary
```

## 수동 검증

pending outbox를 claim하지 않고 미리 보려면:

```bash
./.venv/bin/python scripts/run_google_sync_worker.py --dry-run --limit 5
```

한 batch만 직접 실행하려면:

```bash
./.venv/bin/python scripts/run_google_sync_worker.py --once --limit 5 --max-attempts 5
```

## 중지 / 롤백

```bash
systemctl --user disable --now molly-google-sync-worker.timer
systemctl --user stop molly-google-sync-worker.service
```

timer를 중지해도 local calendar DB와 outbox row는 유지된다. Google 반영만 멈추며, 나중에 다시 켜면 pending row를 이어서 처리한다.

## 주의

- Google API 오류는 Telegram 사용자 응답을 막지 않는다.
- 같은 outbox row는 pending 상태일 때만 claim된다.
- 이미 mapping된 create row는 Google에 다시 insert하지 않고 `done` 처리한다.
- payload detail은 가족 일정 정보를 포함할 수 있으므로 Slack admin/debug 채널에서만 확인한다.
