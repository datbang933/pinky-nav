# CLAUDE.md — pinky-nav 프로젝트 맥락 (Claude Code가 세션 시작 시 자동으로 읽음)

> 변하지 않는 규칙/구조/함정만 여기에. **진행 상황·다음 할 일은 `HANDOFF.md`** 에 있으니 작업 시작 전에 반드시 읽을 것.

## 목표
실제 Pinky Pro(Raspberry Pi)로 SLAM 지도를 만들고, RViz에서 목적지를 찍거나 Python 이벤트(`tools/pinky_nav.py`)로 지정한 위치로 자율주행한다.

## 아키텍처 (분리 원칙)
- **로봇(RPi, `pinky@192.168.4.1`)**: 드라이버만 — `bringup_robot.launch.xml` (라이다 `/scan`, `/odom`, `/tf`, 배터리, `/cmd_vel` 구동).
- **노트북(Ubuntu 24.04 + ROS 2 Jazzy)**: slam_toolbox, Nav2+AMCL, RViz, Python 이벤트 프로그램 — 무거운 계산은 전부 여기서.
- `ROS_DOMAIN_ID=1` (로봇·노트북 동일). 업스트림: `upstream.repos` (`src/pinky_pro` 로 clone, git에는 안 올림).
- 로봇 쪽 `bringup.py` 에 `patches/0001-*.patch` (cmd_vel 0.5초 워치독) 적용 필요.

## 자주 쓰는 명령
`tools/pinky_up.sh [--map ...] [--pose X Y YAW]` 시작 · `tools/pinky_down.sh [--robot]` 종료 · `tools/sync_time.sh` 시계 맞추기(사용자가 직접). 자세한 내용은 `README.md`.

## ⚠ 안전 규칙 (실제 로봇이 움직인다)
- 로봇이 움직이는 동작(주행, 탐색, 목적지 이동)은 **실행 전에 사용자에게 알리고**, 사용자가 옆에서 지켜볼 수 있는지 확인. 새 위치에서는 먼저 `/scan`으로 주변 여유 거리를 확인.
- 주행 전 `/battery/voltage` 확인. **7.0 V 미만이면 주행하지 말고 충전 안내** (6.8 V 이하 저전압 경고음).
- 속도는 낮게(기본 0.1 m/s). 이 환경은 1.5 m 정도의 좁은 방.
- **외부로 나가는 작업(git push, 공개 게시)은 사용자 확인 후.** 공개 저장소다. 개인 이메일/비밀번호/토큰/키를 커밋하지 말 것.
- 로봇 `sudo` 비밀번호는 모르고 저장하지 않는다. 필요한 작업은 사용자가 별도 터미널에서 직접 실행하도록 명령을 안내.

## 연기 감지 데모 (tools/smoke_response.py)
- 연기 감지(YOLO)는 **노트북**에서(`.venv`, CPU), 로봇은 카메라 MJPEG 서버(`:5000`)와 `pinky_led led_server` 만. 코드/로직은 `Evacuator`(순수 파이썬, `tests/` 로 검증) + ROS 연결부.
- 경보 → LED 빨강/파랑 교대 + Nav2 `goto(safe zone)`; 도착하면 초록. `/pinky/smoke` 로 `trigger`/`reset`.
- 모델 가중치(`smoke/models/`)는 라이선스 불명이라 **저장소에 올리지 않는다**. 실제 연기로 정확도는 미검증.
- 로봇 쪽 카메라(pinkylib)/LED 서버 기동은 아직 실물에서 테스트 안 됨 → 첫 실행 시 `/tmp/camera_server.log`, `/tmp/led_server.log`(로봇) 확인.

## 시험장 지도 `maps/arena3` (현재 기준)
- 시험장 **모서리가 (0,0)**, x=1805 mm 쪽, y=1820 mm 쪽. 로봇 시작 위치 **(0.298, 0.195) 앞이 +x**. 모든 로봇이 같은 좌표를 쓴다(로봇 3대가 이 지도를 공유; 각자 위치만 초기 위치로 알려 주면 됨).
- SLAM으로 지도를 만들 때 SLAM 좌표 원점은 로봇 시작점 → 저장 후 `tools/set_map_origin.py maps/X.yaml -0.298 -0.195` 로 모서리 기준으로 옮긴다. (SLAM이 켜져 있는 동안의 `scan_rooms.py`/`explore.py` 좌표는 SLAM 좌표.)
- 시나리오: 2막(병실) = `tools/places/act2.yaml` (병실A=출발 방, 안전지대A=가운데 홀, 병실B=왼쪽 위 방, 안전지대B=오른쪽 아래 방). 1막은 같은 지도에 이름만 다른 `places/act1.yaml` 을 추가.

## 환경 함정 (겪은 것들)
- **로봇이 공유기(`fastcampus`)에 붙은 채 AP를 열면 한 칩이 시간을 나눠 써서 지연이 100~500 ms 로 튀고 AP 채널이 5 GHz DFS(108)로 밀린다** → TF/`map→odom` 이 1~3 s 늦어 Nav2 가 `Transform data too old`/`Failed to make progress`. 로봇에서 `sudo nmcli device disconnect wlan0; sudo nmcli connection modify fastcampus_13F connection.autoconnect no` 로 AP 전용으로. 주행 전 `ping -c30 -i0.2 192.168.4.1` 평균 < 20 ms, 최대 < 100 ms 인지 확인.
- 좁은 곳(벽 10 cm 이내)에 로봇이 끼면 컨트롤러가 `collision ahead` 로 거부(제자리 회전도 불가). 탐색 목표는 벽에서 17 cm 이상(`explore.py --clear 0.17`). 끼었으면 벽에서 멀어지는 방향으로 0.05 m/s 로 짧게 직진해서 뺀다.
- slam_toolbox lifecycle 활성화가 가끔 멈춤 → `tools/start_slam.sh` (map→odom 속도 확인 후 재시도). SLAM 을 재시작하면 지도와 원점이 사라진다.
- `kill`(SIGTERM)을 무시하는 rclpy 프로세스가 있다(`joint_state_publisher`, 우리 파이썬 노드는 SIGTERM 핸들러 추가함).
- **시계 동기화 필수.** 로봇↔노트북 오차가 수백 ms면 AMCL/Nav2가 `extrapolation into the future`/`Transform data too old`로 실패. `pinky_up.sh` 가 0.15 s 초과 시 중단. 로봇 재부팅하면 다시 틀어짐. 시계 설정은 비밀번호 입력 **후** 시간을 가져와야 정확(`sync_time.sh` 가 그렇게 함).
- 라이다는 base_link 기준 **yaw 180°** (뒤쪽 장착). 스캔 각도 해석 시 보정할 것. 높이 약 12.5 cm → 벽은 15 cm 이상.
- **프로세스 종료는 `pkill -x <정확한 이름>`.** `pkill -f`/`pgrep -f` 는 자기 자신의 bash 명령줄에 매칭되어 셸을 죽인다(exit 143/144).
- Nav2 기동이 가끔 멈춤 → `tools/start_nav2.sh` (재시도). SLAM이 먼저, Nav2는 SLAM 뜬 뒤에. 동시에 띄우면 타임아웃.
- slam_toolbox `map→odom` 이 느려지면(1 Hz 미만) 목표가 ABORT → SLAM 노드만 재시작.
- AMCL은 초기 위치 필요. 첫 줄 경고 `Failed to transform initial pose in time` 는 무해.
- Claude Code의 `!` 명령에는 tty가 없어 **비밀번호 입력이 필요한 명령(ssh -t sudo, git push 토큰)은 사용자의 별도 터미널**에서.
- 이 PC의 `credential.helper=store` 에 오래된 토큰이 있으면 push가 403. `git -c credential.helper= push` 로 우회.

## 작업 규칙
- 큰 변화는 `HANDOFF.md` 를 갱신하고 커밋. 지도는 `maps/`, 이름 붙인 목적지는 `tools/places/<시나리오>.yaml` (`PINKY_SCENARIO`, 기본 `act2`; 지도를 바꾸면 좌표 재설정).
- 코드/문서 한국어 설명 OK. 커밋 메시지 끝에는 Claude 공동작성 줄 규칙을 따름.
