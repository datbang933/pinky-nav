#!/usr/bin/env python3
"""Minimal frontier exploration on top of slam_toolbox + Nav2. Usage: explore.py [--max-goals 25] [--max-time 420]"""
import math, time, argparse, numpy as np
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from nav_msgs.msg import OccupancyGrid
from nav2_msgs.action import NavigateToPose
from tf2_ros import Buffer, TransformListener
from scipy import ndimage

ap = argparse.ArgumentParser(); ap.add_argument('--max-goals', type=int, default=25)
ap.add_argument('--max-time', type=float, default=420); ap.add_argument('--clear', type=float, default=0.12)
ap.add_argument('--min-size', type=int, default=3); a = ap.parse_args()

rclpy.init(); n = Node('explore'); tfb = Buffer(); TransformListener(tfb, n)
grid = {}
n.create_subscription(OccupancyGrid, 'map', lambda m: grid.__setitem__('m', m),
    QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL))
ac = ActionClient(n, NavigateToPose, 'navigate_to_pose')

def spin(t=0.1): rclpy.spin_once(n, timeout_sec=t)
def pose():
    for _ in range(100):
        spin(0.05)
        try:
            t = tfb.lookup_transform('map', 'base_footprint', rclpy.time.Time()); p = t.transform.translation; return p.x, p.y
        except Exception: pass
def frontiers():
    m = grid['m']; w, h, r = m.info.width, m.info.height, m.info.resolution
    d = np.array(m.data, dtype=np.int16).reshape(h, w); ox, oy = m.info.origin.position.x, m.info.origin.position.y
    free = d == 0; unk = d == -1; occ = d >= 65
    nb = ndimage.binary_dilation(unk, structure=[[0,1,0],[1,1,1],[0,1,0]]) & free
    clear = ndimage.distance_transform_edt(~occ) * r >= a.clear
    f = nb & clear
    lab, k = ndimage.label(f, structure=np.ones((3,3)))
    out = []
    for i in range(1, k+1):
        rr, cc = np.where(lab == i)
        if len(rr) < a.min_size: continue
        mr, mc = rr.mean(), cc.mean(); j = np.argmin((rr-mr)**2 + (cc-mc)**2)
        out.append((ox+(cc[j]+0.5)*r, oy+(rr[j]+0.5)*r, len(rr)))
    return out, (d != -1).sum() * r * r

while 'm' not in grid: spin(0.5)
if not ac.wait_for_server(15): print('no nav2'); raise SystemExit(1)
black = []; t0 = time.time(); goals = 0; fails = 0
while goals < a.max_goals and time.time()-t0 < a.max_time:
    for _ in range(10): spin(0.1)
    p = pose()
    if not p: print('no pose'); break
    fr, known = frontiers()
    fr = [f for f in fr if all(math.hypot(f[0]-b[0], f[1]-b[1]) > 0.25 for b in black)]
    print(f'[{time.time()-t0:5.0f}s] known={known:.2f} m2 frontiers={len(fr)} robot=({p[0]:.2f},{p[1]:.2f})', flush=True)
    if not fr: print('NO MORE FRONTIERS -> done'); break
    fr.sort(key=lambda f: math.hypot(f[0]-p[0], f[1]-p[1]) - 0.02*f[2])
    gx, gy, sz = fr[0]; yaw = math.atan2(gy-p[1], gx-p[0])
    if math.hypot(gx-p[0], gy-p[1]) < 0.15: black.append((gx, gy)); continue
    g = NavigateToPose.Goal(); g.pose.header.frame_id = 'map'; g.pose.header.stamp = n.get_clock().now().to_msg()
    g.pose.pose.position.x = gx; g.pose.pose.position.y = gy; g.pose.pose.orientation.z = math.sin(yaw/2); g.pose.pose.orientation.w = math.cos(yaw/2)
    print(f'   -> goal ({gx:.2f},{gy:.2f}) size={sz}', flush=True); goals += 1
    fut = ac.send_goal_async(g); rclpy.spin_until_future_complete(n, fut); gh = fut.result()
    if not gh.accepted: black.append((gx, gy)); continue
    rf = gh.get_result_async(); ts = time.time()
    try:
        while not rf.done():
            spin(0.2)
            if time.time()-ts > 60: gh.cancel_goal_async(); print('   goal timeout, cancel'); break
    except KeyboardInterrupt:
        gh.cancel_goal_async(); print('Ctrl-C'); break
    spin(0.5); st = rf.result().status if rf.done() else -1
    print(f'   result status={st} (4=ok)', flush=True)
    if st != 4: black.append((gx, gy)); fails += 1
    if fails >= 6: print('too many failures'); break
print('explore finished; goals sent:', goals, 'blacklisted:', len(black))
