# HANDOFF.md — 진행 상황 인계 (작업 끝날 때마다 갱신)

_마지막 갱신: 2026-11-21 (실제 연기 발생기로 테스트 완료)_

## 지금 상태
- ✅ 실제 로봇 + 노트북 분리 구성 동작 확인 (`/scan` 10 Hz, `/odom` 30 Hz).
- ✅ SLAM 지도 작성 → 자동 탐색(`tools/explore.py`) → 저장. 최신 지도 `maps/room3` (약 1.5 m 닫힌 방, 중앙 장애물 포함). 지도는 테스트 환경을 바꾸면 다시 만들 것.
- ✅ Nav2+AMCL 목적지 이동 확인 (RViz "2D Goal Pose", Python `goto_place('A')`, `/pinky/event` 로 `goto:A`). 도착 오차 약 6~8 cm.
- ✅ `tools/pinky_up.sh` / `pinky_down.sh` 로 한 번에 시작/종료. 경로를 저장소 기준으로 바꾼 뒤 **전체 재실행은 아직 미검증** (로봇이 충전 중이었음).
- ✅ 로봇 `bringup.py` cmd_vel 워치독 패치 (`patches/`).

- ✅ **연기 감지 → 사이렌+안전지대 이동 데모 구현** (`tools/smoke_response.py`, `tools/camera_server.py`, `smoke/`). 검증된 것: 모델 로드/클래스(`smoke`,`fire`)/CPU 34 ms, 로직 단위테스트 4개, 가짜 로봇(LED 서비스+Nav2 액션)으로 ROS 연결부 전체 흐름, 노트북 웹캠으로 카메라 서버→OpenCV 수신 10 fps. **미검증(실물 필요):** 로봇에서 카메라 서버(pinkylib 백엔드)·`led_server` 기동, 실제 LED 점등, Nav2로 안전지대 도달, 실제 연기 검출 정확도.
- ✅ **실물 시나리오 통과**: 지도 `maps/arena` (가벽 시험장, 원점=로봇 시작 위치, x=앞, y=왼쪽, 약 1.9×1.9 m). 안전지대 (1.2, 1.2) 는 빈 칸, 도착 오차 7 cm. 가짜 연기(`trigger`) → LED 빨강/파랑 교대(31 s 동안 39+39회) → 안전지대 → 초록, `reset` 으로 해제. 로봇 카메라(pinkylib) 10 fps 스트림 OK, 감지기 연결 OK. **실제 연기 발생기로 감지 확인**: 연기가 보일 때 `smoke` 신뢰도 0.51~0.73, 연기 없는 45 s 동안 오탐 0 (신뢰도 0.10 이상 감지 없음). 연기가 화면에 잠깐 보일 때는 0.29~0.36 이라 기본값을 `--conf 0.3 --min-hits 3` 으로 낮춤. 로봇 카메라 화면은 청록빛(색 보정 안 됨). 감지 전용 모니터: `tools/smoke_monitor.py` (로봇 안 움직임). **미검증:** 장시간 오탐(조명 변화/수증기), 여러 연기 환경.
- ~~안전지대 (x=1.2, y=1.2) 는 현재 지도 `room3` 밖~~ → `arena` 지도로 해결. (이전 메모: (갈 수 있는 y 최대 0.83 m). 시험장을 정하고 기준점(원점)을 정해 지도를 새로 만들거나 `tools/set_map_origin.py` 로 원점을 옮겨야 했음.)

## 마지막 시점의 로봇 상태
- 배터리 **6.88 V (저전압 경고 직전)** → 충전 필요. 충전 후 `pinky_up.sh` 로 재검증.
- 로봇 시계는 재부팅/장시간 후 틀어짐 → `tools/sync_time.sh`.

## 다음 할 일 (우선순위 순)
0. (완료) 연기 데모 실물 검증 — 남은 것: 오탐 장시간 관찰, 카메라 색 보정, LED 육안 확인. 이전 메모: **연기 데모 실물 검증**: 충전 → `pinky_up.sh --smoke ...` → 카메라 화면 방향/색 확인(`--rotate`, `--swap-rb`) → 가짜 연기 `trigger` 로 LED/이동 확인 → 실제 연기(또는 모니터 영상)로 `--conf`/`--min-hits` 조정. 안전지대 좌표/지도 기준 확정.
1. 충전 후 `pinky_up.sh --map maps/room3.yaml --pose <실제 위치>` 전체 재검증 (경로 리팩터링 확인).
2. **이벤트 연동**: 어떤 이벤트(버튼/카메라/호출 등)로 어디로 보낼지 정해 `tools/pinky_nav.py` 에 붙이기. 연속 이벤트 처리(큐/우선순위)도 설계.
3. 지도 제작 자동화 `tools/pinky_map.sh` (SLAM→Nav2→explore→저장을 한 번에).
4. 시계 동기화 영구화(chrony) — 로봇 sudo 필요(사용자가 직접).
5. Docker화: **노트북 쪽만** (`ros:jazzy`, `--network host`, X11). 로봇은 네이티브 유지. 구성이 안정된 뒤에.
6. 팀원 협업자 추가 / main 브랜치 보호 (GitHub 설정).

## 알려진 이슈
- **공유 Wi-Fi(fastcampus)에서는 TF 지연이 1.7 s까지 튀어 Nav2가 안 뜸** → 반드시 로봇 자체 AP(`pinky_eed0`, 192.168.4.1)로 연결. 부팅 직후 hostapd 가 start-limit 으로 죽는 경우가 있음 → 로봇에서 `sudo systemctl reset-failed hostapd && sudo systemctl restart hostapd`. (공유망용 `tools/robot_ip.txt`, `ROS_STATIC_PEERS` 지원은 넣어 둠)
- 로봇 카메라 화면이 청록빛(색 보정). 감지 정확도에 영향 가능 → 실제 연기로 확인 후 필요하면 보정.
- `pgrep -f`/`pkill -f` 는 자기 명령줄에 걸린다(원격 ssh 명령 포함). 시작 확인은 포트/PID 파일로.
- 로봇 `joint_state_publisher` 는 SIGTERM/SIGINT 를 무시 → `kill -9`.
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
