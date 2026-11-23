#!/usr/bin/env python3
"""Brute-force scan-to-map matching around a guess: finds where the robot REALLY is (cm accuracy) and prints the residual.
usage: scan_match_pose.py [--map maps/arena3] [--guess X Y YAW] [--set]     (--set publishes it as AMCL initial pose)"""
import argparse, math, os, sys, time, numpy as np, yaml
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener
from PIL import Image
from scipy import ndimage
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('--map', default=os.path.join(ROOT, 'maps', 'arena3')); ap.add_argument('--guess', type=float, nargs=3)
ap.add_argument('--radius', type=float, default=0.25); ap.add_argument('--set', action='store_true'); a = ap.parse_args()
meta = yaml.safe_load(open(a.map + '.yaml')); r = meta['resolution']; ox, oy = meta['origin'][:2]
img = np.array(Image.open(a.map + '.pgm')); H, W = img.shape
occ = (img == 0)
dist = ndimage.distance_transform_edt(~occ) * r          # distance to nearest wall cell (m)
rclpy.init(); n = rclpy.create_node('scanmatch'); g = []; tfb = Buffer(); TransformListener(tfb, n)
n.create_subscription(LaserScan, 'scan', lambda m: g.append(m), qos_profile_sensor_data)
t0 = time.time(); guess = a.guess
while time.time() - t0 < 10 and (len(g) < 5 or guess is None):
    rclpy.spin_once(n, timeout_sec=0.05)
    if guess is None:
        try:
            t = tfb.lookup_transform('map', 'base_footprint', rclpy.time.Time()); q = t.transform.rotation; p = t.transform.translation
            guess = (p.x, p.y, math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z)))
        except Exception: pass
if guess is None or not g: sys.exit('no scan or no pose guess')
m = g[-1]; ang = np.array([m.angle_min + i*m.angle_increment for i in range(len(m.ranges))]); rg = np.array(m.ranges)
ok = np.isfinite(rg) & (rg > 0.1) & (rg < 3.0); ang, rg = ang[ok], rg[ok]
LID = (-0.017, 0.0, math.pi)                              # lidar in base frame: x offset, y, yaw
def score(x, y, th):
    lx = x + LID[0]*math.cos(th); ly = y + LID[0]*math.sin(th); a_ = th + LID[2] + ang
    px = lx + rg*np.cos(a_); py = ly + rg*np.sin(a_)
    c = ((px - ox)/r).astype(int); rr = (H - 1 - ((py - oy)/r)).astype(int); v = (c >= 0) & (c < W) & (rr >= 0) & (rr < H)
    d = np.full(len(rg), 0.5); d[v] = dist[rr[v], c[v]]
    return float(np.mean(np.minimum(d, 0.15)))            # mean (clipped) distance of scan hits to the nearest wall
best = None
gx, gy, gth = guess
for dx in np.arange(-a.radius, a.radius+1e-9, 0.01):
    for dy in np.arange(-a.radius, a.radius+1e-9, 0.01):
        for dth in np.radians(np.arange(-20, 20.1, 1.0)):
            s = score(gx+dx, gy+dy, gth+dth)
            if best is None or s < best[0]: best = (s, gx+dx, gy+dy, gth+dth)
s0 = score(gx, gy, gth)
print('guess  (%.2f, %.2f, %.0f deg): mean scan-to-wall distance %.1f cm' % (gx, gy, math.degrees(gth), s0*100))
print('BEST   (%.2f, %.2f, %.0f deg): mean scan-to-wall distance %.1f cm   -> shift (%+.0f, %+.0f) cm, %+.0f deg' % (best[1], best[2], math.degrees(best[3]), best[0]*100, (best[1]-gx)*100, (best[2]-gy)*100, math.degrees(best[3]-gth)))
if a.set:
    import subprocess
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'set_initial_pose.py'), '%.3f' % best[1], '%.3f' % best[2], '%.3f' % best[3]])
n.destroy_node(); rclpy.shutdown()
