#!/usr/bin/env python3
"""Visit the centre of every room and do a 360-degree in-place scan (fills shadows / unseen corners while SLAM runs).
Places are given in ARENA coordinates (origin = arena corner); --offset converts to the SLAM map frame
(SLAM origin = robot start pose = arena (0.298, 0.195)).  usage: scan_rooms.py [--offset 0.298 0.195]"""
import argparse, math, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pinky_nav import PinkyNav
from nav2_msgs.action import Spin
from rclpy.action import ActionClient
from builtin_interfaces.msg import Duration

ROOMS = [  # (name, arena x, y)  -- room centres read off maps/arena3
    ('upper-right room', 1.35, 1.50),
    ('lower-right room', 1.40, 0.30),
    ('origin room (lower-left)', 0.45, 0.30),
    ('upper-left room', 0.45, 1.50),
    ('middle hall', 0.90, 0.85),
]
ap = argparse.ArgumentParser(); ap.add_argument('--offset', type=float, nargs=2, default=[0.298, 0.195])
a = ap.parse_args(); ox, oy = a.offset
nav = PinkyNav(); spin = ActionClient(nav, Spin, 'spin'); spin.wait_for_server(10)
ok_all = True
try:
    for name, x, y in ROOMS:
        p = nav.pose(); print(f'-> {name}: arena ({x:.2f},{y:.2f})  from ({p[0]+ox:.2f},{p[1]+oy:.2f})', flush=True)
        t = time.time(); ok = nav.goto(x - ox, y - oy, 0.0, timeout=120); q = nav.pose()
        print(f'   goto {"ARRIVED" if ok else "FAILED"} {time.time()-t:.0f}s at arena ({q[0]+ox:.2f},{q[1]+oy:.2f})', flush=True)
        if not ok: ok_all = False; continue
        g = Spin.Goal(); g.target_yaw = 2 * math.pi - 0.05; g.time_allowance = Duration(sec=40)
        fut = spin.send_goal_async(g)
        while not fut.done(): time.sleep(0.05)
        gh = fut.result()
        if not gh.accepted: print('   spin rejected'); ok_all = False; continue
        res = gh.get_result_async()
        while not res.done(): time.sleep(0.1)
        print(f'   spin status {res.result().status} (4=ok)', flush=True)
finally:
    nav.close()
print('ALL ROOMS SCANNED' if ok_all else 'SOME ROOMS FAILED')
