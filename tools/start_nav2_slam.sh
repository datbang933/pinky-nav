#!/bin/bash
# Nav2 (navigation only, no AMCL) next to a running slam_toolbox, with retries (new DDS participants need a few seconds to find the robot)
source "$(dirname "$(readlink -f "$0")")/pinky_env.sh"
NAVPIDS=/tmp/pinky_nav_slam.pids
stop_nav() { for c in controller_serv planner_server behavior_server bt_navigator smoother_server lifecycle_manag waypoint_foll velocity_smoot; do pkill -x $c; done
             [ -f $NAVPIDS ] && kill $(cat $NAVPIDS) 2>/dev/null; rm -f $NAVPIDS; sleep 2; }
for try in 1 2 3 4; do
  stop_nav
  setsid nohup ros2 launch pinky_navigation navigation_launch.xml params_file:=$PINKY_TOOLS/nav2_room.yaml > /tmp/nav.log 2>&1 < /dev/null & echo $! > $NAVPIDS
  for i in $(seq 1 30); do
    sleep 2
    grep -q "Managed nodes are active" /tmp/nav.log && { echo "nav2 active (try $try)"; exit 0; }
    grep -q "Aborting bringup" /tmp/nav.log && break
  done
  echo "try $try failed: $(grep -E 'ERROR' /tmp/nav.log | grep -vE 'QoS' | head -n1 | cut -c1-150)"
done
echo "nav2 FAILED"; exit 1
