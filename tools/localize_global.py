#!/usr/bin/env python3
"""Find the robot on the map without knowing where it is: AMCL global localization + one 360 deg in-place spin.
usage: localize_global.py [--no-spin]       (needs Nav2/AMCL running; robot may be anywhere inside the arena)
Prints the converged pose and its uncertainty."""
import argparse, math, sys, time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from std_srvs.srv import Empty
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav2_msgs.action import Spin
from builtin_interfaces.msg import Duration
import threading

ap = argparse.ArgumentParser(); ap.add_argument('--no-spin', action='store_true'); ap.add_argument('--max-std', type=float, default=0.10)
a = ap.parse_args()
rclpy.init(); n = Node('localize_global'); last = {}
n.create_subscription(PoseWithCovarianceStamped, 'amcl_pose', lambda m: last.__setitem__('p', m), 10)
ex = SingleThreadedExecutor(); ex.add_node(n); th = threading.Thread(target=ex.spin, daemon=True); th.start()
def shutdown():
    ex.shutdown(); th.join(timeout=2); n.destroy_node(); rclpy.shutdown()
cli = n.create_client(Empty, 'reinitialize_global_localization')
if not cli.wait_for_service(10): shutdown(); sys.exit('AMCL service not available (is Nav2/AMCL running?)')
fut = cli.call_async(Empty.Request()); t0 = time.time()
while not fut.done() and time.time() - t0 < 10: time.sleep(0.05)
print('global localization started: particles spread over the whole map')
last.clear()
if not a.no_spin:
    sp = ActionClient(n, Spin, 'spin')
    if sp.wait_for_server(5):
        g = Spin.Goal(); g.target_yaw = 2 * math.pi - 0.05; g.time_allowance = Duration(sec=40)
        f = sp.send_goal_async(g)
        while not f.done(): time.sleep(0.05)
        r = f.result().get_result_async()
        while not r.done(): time.sleep(0.1)
        print('spin status', r.result().status, '(4=ok)')
t0 = time.time(); ok = False
while time.time() - t0 < 25:
    time.sleep(0.5); m = last.get('p')
    if m is None: continue
    c = m.pose.covariance; sx, sy, sth = math.sqrt(max(c[0], 0)), math.sqrt(max(c[7], 0)), math.sqrt(max(c[35], 0))
    p = m.pose.pose; q = p.orientation; yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
    if max(sx, sy) < a.max_std: ok = True; break
if 'p' not in last: print('no amcl_pose received'); shutdown(); sys.exit(2)
print('%s pose (map/arena frame): x=%.2f y=%.2f yaw=%.0f deg   std x=%.2f y=%.2f m, yaw=%.0f deg' % ('CONVERGED' if ok else 'NOT CONVERGED', p.position.x, p.position.y, math.degrees(yaw), sx, sy, math.degrees(sth)))
shutdown(); sys.exit(0 if ok else 1)
