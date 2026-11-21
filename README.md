# Pinky Pro 자율주행 (SLAM 지도 → 목적지 이동)

Pinky Pro(Raspberry Pi)는 **센서/모터 드라이버만** 실행하고, SLAM·Nav2·RViz·이벤트 프로그램은 **노트북**에서 실행합니다.
공식 패키지 [`pinklab-art/pinky_pro`](https://github.com/pinklab-art/pinky_pro) 위에 얹은 실행 스크립트·이벤트 API·지도 모음입니다.

```
 Pinky (RPi, 192.168.4.1)                      노트북 (Ubuntu 24.04 + ROS 2 Jazzy)
 ├ sllidar  ──/scan──────────────────────────► slam_toolbox (지도 작성) / AMCL (위치추정)
 ├ bringup  ──/odom, /tf────────────────────► Nav2 (planner·controller·costmap)
 └ bringup  ◄──/cmd_vel──────────────────────  RViz "2D Goal Pose" / pinky_nav.py (Python 이벤트)
```

## 구성

| 경로 | 내용 |
|---|---|
| `tools/pinky_up.sh` / `pinky_down.sh` | 전체 시작 / 종료 (로봇 bringup → Nav2+AMCL → 초기 위치 → RViz → 이벤트 리스너) |
| `tools/sync_time.sh` | 로봇 시계를 노트북 기준으로 맞춤 (**직접 실행, 로봇 sudo 비밀번호 필요**) |
| `tools/pinky_nav.py` | Python API (`goto`, `goto_place`, `cancel`) + `/pinky/event` 리스너 |
| `tools/places.yaml` | 이름 붙인 목적지 (지도 좌표) — 지도를 바꾸면 다시 정해야 함 |
| `tools/explore.py` | 프런티어 자동 탐색 (SLAM+Nav2 실행 중에 지도를 자동 완성) |
| `tools/nav2_room.yaml` | 좁은 공간용 Nav2 파라미터 (속도 0.1 m/s, 도착 허용 8 cm) |
| `tools/drive_square.py` | 오도메트리 기반 사각형 주행 (안전 정지 포함) |
| `maps/` | 저장된 지도 (`room2`, `room3`) |
| `patches/` | 업스트림에 적용할 패치 (로봇 쪽에 적용해야 함) |
| `upstream.repos` | 업스트림 저장소 정보 |

## 설치

### 노트북
```bash
mkdir -p ~/pinky_pro/src && cd ~/pinky_pro
git clone <이 저장소 URL> .            # 또는 이 저장소를 ~/pinky_pro 로
git clone https://github.com/pinklab-art/pinky_pro.git src/pinky_pro
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
sudo apt install python3-scipy python3-pil python3-yaml
```

### 로봇 (한 번만) — cmd_vel 안전 타임아웃 패치
업스트림 `bringup.py`는 `cmd_vel`이 끊겨도 마지막 속도로 계속 달립니다. 0.5초 동안 명령이 없으면 정지하도록 패치합니다.
```bash
ssh pinky@192.168.4.1
cd ~/pinky_pro/src/pinky_pro && patch -p1 < <저장소>/patches/0001-bringup-cmd_vel-watchdog.patch
cd ~/pinky_pro && colcon build --packages-select pinky_bringup
```
로봇의 `ROS_DOMAIN_ID`는 `1`입니다(`~/.bashrc`). 노트북도 같은 값을 씁니다(`tools/pinky_env.sh`).

## 사용

```bash
# 1) 로봇 시계 맞추기 (재부팅 후 / pinky_up.sh 가 요구할 때, 직접 실행)
tools/sync_time.sh

# 2) 시작 — 마지막 위치를 초기 위치로 사용. 로봇을 손으로 옮겼다면 --pose 지정
tools/pinky_up.sh --map maps/room3.yaml [--pose X Y YAW]

# 3) 목적지 지정
#    - RViz: "2D Goal Pose" 로 클릭+드래그 (위치가 틀어지면 "2D Pose Estimate")
#    - 이벤트: ros2 topic pub --once /pinky/event std_msgs/msg/String "{data: 'goto:A'}"
#    - Python:  from pinky_nav import PinkyNav; PinkyNav().goto_place('A')

# 4) 종료
tools/pinky_down.sh [--robot]
```

### 새 지도 만들기
로봇 bringup 실행 후 (SLAM을 먼저, Nav2는 SLAM이 뜬 뒤에 실행해야 안정적):
```bash
ros2 launch pinky_navigation map_building.launch.xml &
ros2 launch pinky_navigation navigation_launch.xml params_file:=tools/nav2_room.yaml &
python3 tools/explore.py              # 자동 탐색
ros2 run nav2_map_server map_saver_cli -f maps/<이름>
```
- 라이다 높이는 바닥에서 약 12.5 cm → **벽/장애물 높이 15 cm 이상(권장 20 cm)**, 불투명 재질.

## 알려진 이슈 / 주의

- **시계 동기화가 필수**입니다. 로봇↔노트북 오차가 수백 ms를 넘으면 AMCL/Nav2가 TF 오류로 동작하지 않습니다. (영구 해결: chrony 설정 — 미적용)
- slam_toolbox의 `map→odom` 갱신이 가끔 느려져 Nav2 목표가 ABORT 됩니다. SLAM 노드만 재시작하면 복구됩니다.
- Nav2 기동이 가끔 멈춥니다. `tools/start_nav2.sh` 가 자동 재시도합니다.
- **배터리**: 약 6.8 V 이하이면 저전압 경고(삐삐)가 납니다. 주행 전 `/battery/voltage` 확인, 7.0 V 아래면 충전하세요.
- 목적지 이벤트가 연속으로 들어오면 새 목표가 이전 목표를 덮어씁니다 (큐 없음).
- 로봇 이동 중에는 항상 옆에서 지켜보세요. 키/명령이 끊기면 0.5초 뒤 정지합니다(패치 적용 시).
