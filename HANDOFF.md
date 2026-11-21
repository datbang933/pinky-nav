# HANDOFF.md — 진행 상황 인계 (작업 끝날 때마다 갱신)

_마지막 갱신: 2026-11-21_

## 지금 상태
- ✅ 실제 로봇 + 노트북 분리 구성 동작 확인 (`/scan` 10 Hz, `/odom` 30 Hz).
- ✅ SLAM 지도 작성 → 자동 탐색(`tools/explore.py`) → 저장. 최신 지도 `maps/room3` (약 1.5 m 닫힌 방, 중앙 장애물 포함). 지도는 테스트 환경을 바꾸면 다시 만들 것.
- ✅ Nav2+AMCL 목적지 이동 확인 (RViz "2D Goal Pose", Python `goto_place('A')`, `/pinky/event` 로 `goto:A`). 도착 오차 약 6~8 cm.
- ✅ `tools/pinky_up.sh` / `pinky_down.sh` 로 한 번에 시작/종료. 경로를 저장소 기준으로 바꾼 뒤 **전체 재실행은 아직 미검증** (로봇이 충전 중이었음).
- ✅ 로봇 `bringup.py` cmd_vel 워치독 패치 (`patches/`).

## 마지막 시점의 로봇 상태
- 배터리 **6.88 V (저전압 경고 직전)** → 충전 필요. 충전 후 `pinky_up.sh` 로 재검증.
- 로봇 시계는 재부팅/장시간 후 틀어짐 → `tools/sync_time.sh`.

## 다음 할 일 (우선순위 순)
1. 충전 후 `pinky_up.sh --map maps/room3.yaml --pose <실제 위치>` 전체 재검증 (경로 리팩터링 확인).
2. **이벤트 연동**: 어떤 이벤트(버튼/카메라/호출 등)로 어디로 보낼지 정해 `tools/pinky_nav.py` 에 붙이기. 연속 이벤트 처리(큐/우선순위)도 설계.
3. 지도 제작 자동화 `tools/pinky_map.sh` (SLAM→Nav2→explore→저장을 한 번에).
4. 시계 동기화 영구화(chrony) — 로봇 sudo 필요(사용자가 직접).
5. Docker화: **노트북 쪽만** (`ros:jazzy`, `--network host`, X11). 로봇은 네이티브 유지. 구성이 안정된 뒤에.
6. 팀원 협업자 추가 / main 브랜치 보호 (GitHub 설정).

## 알려진 이슈
- slam_toolbox `map→odom` 갱신이 가끔 느려져 Nav2 목표가 ABORT (SLAM 재시작으로 복구, 근본 원인 미확인).
- Nav2 기동이 가끔 멈춤 (`start_nav2.sh` 가 재시도).
- 이벤트가 연속으로 오면 새 목표가 이전 목표를 덮어씀.
- 지금 경로는 사각형 방 하나만 검증됨 (좁은 통로/큰 공간은 미검증 — 속도·허용오차 `tools/nav2_room.yaml` 조정 필요).

## 결정 기록
- 무거운 처리는 노트북, 로봇은 드라이버만 (사용자 요구).
- Docker는 지금 하지 않고 안정화 후 노트북 쪽만.
- 업스트림 `pinky_pro` 는 저장소에 복사하지 않고 `upstream.repos` + 패치로 관리.
- 공개 저장소(`datbang933/pinky-nav`), 커밋 작성자는 GitHub noreply 주소 (개인 이메일 비공개).

## 새 PC에서 이어가는 법
1. `git clone https://github.com/datbang933/pinky-nav.git ~/pinky_pro` → README의 설치 절차 (업스트림 clone, rosdep, colcon build).
2. 같은 네트워크(로봇 AP `192.168.4.x`)에 접속, 로봇 SSH 키 등록(`ssh-copy-id pinky@192.168.4.1`, 비밀번호는 담당자에게).
3. 저장소 폴더에서 Claude Code 실행 → `CLAUDE.md` 가 자동 로드됨. 첫 메시지로 "HANDOFF.md 읽고 이어서 작업하자" 라고 말하면 됨.
