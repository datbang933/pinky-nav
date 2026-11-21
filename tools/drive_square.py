#!/usr/bin/env python3
"""Drive a square (side L m) using odom feedback. Safe: slow, lidar stop, watchdog-friendly (20Hz cmd), Ctrl-C stops.
usage: drive_square.py [--side 2.0] [--dry]"""
import math, sys, time, argparse
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener

ap = argparse.ArgumentParser(); ap.add_argument('--side', type=float, default=2.0)
ap.add_argument('--v', type=float, default=0.10); ap.add_argument('--w', type=float, default=0.4)
ap.add_argument('--stop', type=float, default=0.30); ap.add_argument('--dry', action='store_true')
a = ap.parse_args()

def yaw(q): return math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
def wrap(x): return math.atan2(math.sin(x), math.cos(x))

class D(Node):
    def __init__(s):
        super().__init__('drive_square')
        s.pub = s.create_publisher(Twist, 'cmd_vel', 10)
        s.odom = None; s.scan = None
        s.create_subscription(Odometry, 'odom', lambda m: setattr(s, 'odom', m), 10)
        s.create_subscription(LaserScan, 'scan', lambda m: setattr(s, 'scan', m), qos_profile_sensor_data)
        s.tfb = Buffer(); s.tfl = TransformListener(s.tfb, s)
    def spin(s, t=0.05): rclpy.spin_once(s, timeout_sec=t)
    def pose(s):
        p = s.odom.pose.pose; return p.position.x, p.position.y, yaw(p.orientation)
    def send(s, v, w):
        m = Twist(); m.linear.x = v; m.angular.z = w; s.pub.publish(m)
    def front_min(s, lidar_yaw, half=math.radians(25)):
        """min lidar range within +-half of base forward (base +x), given lidar yaw in base frame"""
        sc = s.scan; best = 9.9
        for i, r in enumerate(sc.ranges):
            if not (math.isfinite(r) and r > 0.08): continue
            ang = wrap(sc.angle_min + i*sc.angle_increment + lidar_yaw)
            if abs(ang) <= half: best = min(best, r)
        return best
    def stop(s):
        for _ in range(5): s.send(0.0, 0.0); time.sleep(0.05)

rclpy.init(); n = D()
t0 = time.time()
while (n.odom is None or n.scan is None) and time.time()-t0 < 5: n.spin()
if n.odom is None or n.scan is None: print('FAIL: no odom/scan'); sys.exit(1)
lyaw = 0.0
for _ in range(60):
    n.spin(0.1)
    try:
        t = n.tfb.lookup_transform('base_link', n.scan.header.frame_id, rclpy.time.Time())
        lyaw = yaw(t.transform.rotation); break
    except Exception: pass
print(f'lidar yaw in base_link = {math.degrees(lyaw):.1f} deg; front min = {n.front_min(lyaw):.2f} m')
if a.dry: sys.exit(0)

def go():
    x0, y0, _ = n.pose(); last = (x0, y0, time.time()); t0 = time.time()
    while True:
        n.spin(0.02); x, y, _ = n.pose(); d = math.hypot(x-x0, y-y0)
        if d >= a.side: return True
        if n.front_min(lyaw) < a.stop: print(f'OBSTACLE at {n.front_min(lyaw):.2f} m -> stop, d={d:.2f}'); return False
        if time.time()-t0 > 3 and d < 0.02: print('ABORT: no movement detected'); return False
        if time.time()-t0 > a.side/a.v*2+10: print('ABORT: timeout'); return False
        n.send(a.v if d < a.side-0.05 else a.v*0.5, 0.0); time.sleep(0.05)

def turn(deg):
    _, _, th0 = n.pose(); tgt = math.radians(deg); t0 = time.time()
    while True:
        n.spin(0.02); _, _, th = n.pose(); rem = tgt - wrap(th-th0) if abs(deg) < 180 else tgt - wrap(th-th0)
        done = abs(wrap(th-th0) - tgt) < math.radians(3)
        if done: return True
        if time.time()-t0 > abs(tgt)/a.w*2+8: print('ABORT: turn timeout'); return False
        err = wrap(tgt - wrap(th-th0)); n.send(0.0, math.copysign(max(0.15, min(a.w, abs(err))), err)); time.sleep(0.05)

ok = True
try:
    for i in range(4):
        print(f'side {i+1}/4: forward {a.side} m'); ok = go(); n.stop()
        if not ok: break
        time.sleep(0.5)
        print('turn +90'); ok = turn(90); n.stop()
        if not ok: break
        time.sleep(0.5)
except KeyboardInterrupt:
    print('Ctrl-C'); ok = False
finally:
    n.stop()
print('DONE' if ok else 'STOPPED EARLY'); x, y, th = n.pose(); print(f'final odom: x={x:.2f} y={y:.2f} yaw={math.degrees(th):.0f}')
