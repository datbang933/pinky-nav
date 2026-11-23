#!/bin/bash
# usage: start_nav2.sh <map.yaml> ; starts Nav2+AMCL on the laptop, retries if startup hangs
TOOLS="$(dirname "$(readlink -f "$0")")"; ROOT="$(dirname "$TOOLS")"
MAP=${1:-$ROOT/maps/arena3.yaml}
source /opt/ros/jazzy/setup.bash; source $ROOT/install/setup.bash; export ROS_DOMAIN_ID=1
for try in 1 2 3; do
  pkill -x ros2; for c in sync_slam_toolb lifecycle_manag controller_serv planner_server behavior_serve bt_navigator waypoint_foll velocity_smoot smoother_server component_conta amcl map_server; do pkill -x $c; done
  sleep 3
  setsid nohup ros2 launch pinky_navigation bringup_launch.xml map:=$MAP params_file:=$TOOLS/nav2_room.yaml > /tmp/nav2.log 2>&1 < /dev/null &
  for i in $(seq 1 40); do
    sleep 2
    [ "$(grep -c 'Managed nodes are active' /tmp/nav2.log)" -ge 2 ] && { echo "nav2 active (try $try, ~$((i*2))s)"; exit 0; }
  done
  echo "try $try hung, restarting"
done
echo "nav2 FAILED"; exit 1
