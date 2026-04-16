# Reminder Worker Runtime

## 권장 운영 방식

현재 Molly의 reminder / daily summary / tomorrow summary 는 다음 worker가 담당한다.

- `scripts/run_reminder_worker.py`

이 worker는 이제 `bot.py`와 분리되었으므로, 실운영에서는 별도 장기 실행 프로세스로 띄워야 한다.

가장 권장하는 방식은:

- `systemd --user`

이다.

## 왜 `systemd --user`가 좋은가

- 로그인 사용자 단위 서비스로 관리할 수 있다
- 재부팅 이후 자동 시작 설정이 쉽다
- 프로세스가 죽어도 자동 재시작할 수 있다
- `status`, `restart`, `logs` 확인이 편하다

## repo에 추가한 파일

- `deploy/systemd/molly-reminder-worker.service`

이 서비스는 Molly 프로젝트 루트에서 다음 명령을 실행한다.

```bash
/home/sunghwan/projects/Molly/.venv/bin/python /home/sunghwan/projects/Molly/scripts/run_reminder_worker.py
```

## 설치 개념

일반적인 흐름은 다음과 같다.

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/molly-reminder-worker.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now molly-reminder-worker.service
```

## 자주 쓰는 명령

상태 확인:

```bash
systemctl --user status molly-reminder-worker.service
```

재시작:

```bash
systemctl --user restart molly-reminder-worker.service
```

중지:

```bash
systemctl --user stop molly-reminder-worker.service
```

로그 보기:

```bash
journalctl --user -u molly-reminder-worker.service -n 100 --no-pager
```

## 대안

임시로는 `tmux`로도 운영할 수 있다.

```bash
tmux new -s molly-reminder
./.venv/bin/python scripts/run_reminder_worker.py
```

하지만 장기 운영은 `systemd --user`가 더 낫다.
