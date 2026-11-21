#!/bin/bash
# usage: pinky_down.sh [--robot]   stops laptop side (and robot bringup with --robot); remembers last pose
source "$(dirname "$(readlink -f "$0")")/pinky_env.sh"
python3 - > $PINKY_TOOLS/last_pose.tmp <<'P'
import rclpy,math
from tf2_ros import Buffer,TransformListener
rclpy.init(); n=rclpy.create_node('p'); b=Buffer(); TransformListener(b,n)
for _ in range(150):
    rclpy.spin_once(n,timeout_sec=0.05)
    try:
        t=b.lookup_transform('map','base_footprint',rclpy.time.Time()); q=t.transform.rotation; p=t.transform.translation
        print(round(p.x,3),round(p.y,3),round(math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)),3)); break
    except Exception: pass
P
[ -s $PINKY_TOOLS/last_pose.tmp ] && mv $PINKY_TOOLS/last_pose.tmp $PINKY_TOOLS/last_pose.txt && echo "saved pose: $(cat $PINKY_TOOLS/last_pose.txt)" || rm -f $PINKY_TOOLS/last_pose.tmp
pkill -f "pinky_nav.py listen"; pkill -x rviz2; pkill -x ros2
for c in sync_slam_toolb lifecycle_manag controller_serv planner_server behavior_serve bt_navigator waypoint_foll velocity_smoot smoother_serve component_conta amcl map_server; do pkill -x $c; done
if [ "$1" = "--robot" ]; then ssh $PINKY_HOST 'kill -INT $(cat /tmp/pinky_bringup.pid) 2>/dev/null; sleep 2; pkill -x bringup; pkill -x sllidar_node; true'; echo "robot bringup stopped"; fi
echo "stopped."
