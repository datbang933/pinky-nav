#!/bin/bash
# start slam_toolbox and verify it really publishes map->odom (its lifecycle activation sometimes hangs) — retries
source "$(dirname "$(readlink -f "$0")")/pinky_env.sh"
PIDS=/tmp/pinky_slam.pids
rate() { python3 - <<'P'
import rclpy,time
from tf2_msgs.msg import TFMessage
rclpy.init(); n=rclpy.create_node('t'); c=[0]
n.create_subscription(TFMessage,'/tf',lambda m:c.__setitem__(0,c[0]+sum(1 for t in m.transforms if t.child_frame_id=='odom' and t.header.frame_id=='map')),100)
t0=time.time()
while time.time()-t0<3: rclpy.spin_once(n,timeout_sec=0.05)
print(int(c[0]/3))
P
}
for try in 1 2 3 4; do
  pkill -x sync_slam_toolb; [ -f $PIDS ] && kill $(cat $PIDS) 2>/dev/null; sleep 2
  setsid nohup ros2 launch pinky_navigation map_building.launch.xml > /tmp/slam.log 2>&1 < /dev/null & echo $! > $PIDS
  sleep 8
  r=$(rate); echo "try $try: map->odom ${r} Hz"
  [ "${r:-0}" -ge 5 ] && { echo "slam OK"; exit 0; }
done
echo "slam FAILED"; exit 1
