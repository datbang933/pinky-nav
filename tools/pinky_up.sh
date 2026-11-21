#!/bin/bash
# usage: pinky_up.sh [--map /path/map.yaml] [--pose X Y YAW] [--no-rviz]
# Starts: robot bringup (RPi) -> Nav2+AMCL (laptop) -> initial pose -> RViz -> event listener
source "$(dirname "$(readlink -f "$0")")/pinky_env.sh"
MAP=$PINKY_ROOT/maps/room3.yaml; POSE=""; RVIZ=1
while [ $# -gt 0 ]; do case $1 in --map) MAP=$2; shift 2;; --pose) POSE="$2 $3 $4"; shift 4;; --no-rviz) RVIZ=0; shift;; *) echo "unknown arg $1"; exit 1;; esac; done
[ -z "$POSE" ] && [ -f $PINKY_TOOLS/last_pose.txt ] && POSE=$(cat $PINKY_TOOLS/last_pose.txt); [ -z "$POSE" ] && POSE="0 0 0"
[ -f "$MAP" ] || { echo "map not found: $MAP"; exit 1; }

echo "[1/6] robot reachable?"; ssh -o BatchMode=yes -o ConnectTimeout=5 $PINKY_HOST true || { echo "cannot ssh to $PINKY_HOST"; exit 1; }

echo "[2/6] clock offset"
pgrep -f "tools/timeserver.py" >/dev/null || (setsid nohup python3 $PINKY_TOOLS/timeserver.py >/dev/null 2>&1 </dev/null &); sleep 1
OFF=$(ssh $PINKY_HOST "a=\$(date +%s.%N); t=\$(curl -s http://$LAPTOP_IP:8765); b=\$(date +%s.%N); python3 -c \"print(((\$a+\$b)/2-\$t))\"")
echo "      robot - laptop = $OFF s"
python3 -c "import sys; sys.exit(0 if abs($OFF)<0.15 else 1)" || { echo "CLOCK OFF by >0.15s. Run in a terminal:  $PINKY_TOOLS/sync_time.sh   then re-run pinky_up.sh"; exit 1; }

echo "[3/6] robot bringup"
if ssh $PINKY_HOST 'pgrep -x bringup >/dev/null'; then echo "      already running"; else
  ssh $PINKY_HOST 'bash -lc "source /opt/ros/jazzy/setup.bash; source ~/pinky_pro/install/local_setup.bash; export ROS_DOMAIN_ID=1; setsid nohup ros2 launch pinky_bringup bringup_robot.launch.xml > /tmp/bringup.log 2>&1 < /dev/null & echo \$! > /tmp/pinky_bringup.pid"'
fi
for i in $(seq 1 30); do timeout 3 ros2 topic echo --once /odom --field header.frame_id >/dev/null 2>&1 && { echo "      /odom OK"; break; }; sleep 1; [ $i = 30 ] && { echo "no /odom from robot"; exit 1; }; done

echo "[4/6] Nav2 + AMCL ($MAP)"; $PINKY_TOOLS/start_nav2.sh $MAP || exit 1
echo "[5/6] initial pose: $POSE"; python3 $PINKY_TOOLS/set_initial_pose.py $POSE
if [ $RVIZ = 1 ]; then echo "[6/6] RViz + event listener"; DISPLAY=${DISPLAY:-:0} setsid nohup ros2 launch pinky_navigation nav2_view.launch.xml > /tmp/rviz.log 2>&1 < /dev/null & else echo "[6/6] event listener"; fi
pkill -f "pinky_nav.py listen" 2>/dev/null; setsid nohup python3 $PINKY_TOOLS/pinky_nav.py listen > /tmp/listen.log 2>&1 < /dev/null &
sleep 3; echo; echo "READY.  RViz: '2D Goal Pose' to click goals.  Event:  ros2 topic pub --once /pinky/event std_msgs/msg/String \"{data: 'goto:A'}\""
