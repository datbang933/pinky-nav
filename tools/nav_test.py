import math, time, sys, numpy as np, yaml
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from geometry_msgs.msg import PoseWithCovarianceStamped, PoseStamped
from nav2_msgs.action import NavigateToPose
from tf2_ros import Buffer, TransformListener
from PIL import Image
from scipy import ndimage

import os
mp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'maps', 'room3')
meta = yaml.safe_load(open(mp+'.yaml')); res = meta['resolution']; ox, oy = meta['origin'][:2]
a = np.array(Image.open(mp+'.pgm')); H = a.shape[0]
free = a >= 250
dist = ndimage.distance_transform_edt(free) * res   # distance to nearest non-free
def cell_to_xy(r, c): return ox + (c+0.5)*res, oy + (H-r-0.5)*res

rclpy.init(); n = Node('navtest')
tfb = Buffer(); TransformListener(tfb, n)
def pose():
    for _ in range(50):
        rclpy.spin_once(n, timeout_sec=0.05)
        try:
            t = tfb.lookup_transform('map', 'base_footprint', rclpy.time.Time())
            q = t.transform.rotation; p = t.transform.translation
            return p.x, p.y, math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
        except Exception: pass
    return None

x0, y0, th0 = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
ip = n.create_publisher(PoseWithCovarianceStamped, 'initialpose', QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL))
m = PoseWithCovarianceStamped(); m.header.frame_id = 'map'
m.pose.pose.position.x = x0; m.pose.pose.position.y = y0
m.pose.pose.orientation.z = math.sin(th0/2); m.pose.pose.orientation.w = math.cos(th0/2)
m.pose.covariance[0] = m.pose.covariance[7] = 0.05; m.pose.covariance[35] = 0.05
for _ in range(5): m.header.stamp = n.get_clock().now().to_msg(); ip.publish(m); rclpy.spin_once(n, timeout_sec=0.3)
time.sleep(2)
p = pose(); print('AMCL pose (map->base):', None if p is None else [round(v,3) for v in p])

# pick goal: free cell with clearance >= 0.18 m, 0.45..0.9 m from robot, farthest-first
best = None
for r in range(H):
    for c in range(a.shape[1]):
        if dist[r, c] >= 0.18:
            gx, gy = cell_to_xy(r, c); d = math.hypot(gx-x0, gy-y0)
            if 0.45 <= d <= 0.9 and (best is None or dist[r, c] > best[0]): best = (dist[r, c], gx, gy, d)
print('goal', best)
if len(sys.argv) > 4 and sys.argv[4] == 'dry': sys.exit(0)
_, gx, gy, _ = best
ac = ActionClient(n, NavigateToPose, 'navigate_to_pose'); ac.wait_for_server(10)
g = NavigateToPose.Goal(); g.pose.header.frame_id = 'map'; g.pose.header.stamp = n.get_clock().now().to_msg()
g.pose.pose.position.x = gx; g.pose.pose.position.y = gy
yaw = math.atan2(gy-y0, gx-x0); g.pose.pose.orientation.z = math.sin(yaw/2); g.pose.pose.orientation.w = math.cos(yaw/2)
fut = ac.send_goal_async(g); rclpy.spin_until_future_complete(n, fut); gh = fut.result()
print('goal accepted:', gh.accepted)
if not gh.accepted: sys.exit(1)
rf = gh.get_result_async(); t0 = time.time()
try:
    while not rf.done():
        rclpy.spin_once(n, timeout_sec=0.2); 
        if int((time.time()-t0)*2) % 4 == 0:
            p = pose();
            if p: print(f'  t={time.time()-t0:4.1f}s pose=({p[0]:.2f},{p[1]:.2f}) dist_to_goal={math.hypot(gx-p[0],gy-p[1]):.2f}', flush=True)
        if time.time()-t0 > 90: print('TIMEOUT -> cancel'); gh.cancel_goal_async(); break
except KeyboardInterrupt:
    gh.cancel_goal_async()
rclpy.spin_until_future_complete(n, rf, timeout_sec=5)
print('result status:', rf.result().status if rf.done() else None, '(4=SUCCEEDED, 5=CANCELED, 6=ABORTED)')
p = pose(); print('final', [round(v,3) for v in p], 'goal', round(gx,2), round(gy,2), 'err', round(math.hypot(gx-p[0],gy-p[1]),3))
