#!/usr/bin/env python3
"""Detect-only smoke monitor (robot does NOT move). Shows how confident the model is while you make smoke.
    .venv/bin/python tools/smoke_monitor.py --seconds 120
Output every 2 s: frames, max smoke/fire confidence, detections above the alarm threshold.
Saves: /tmp/smoke_best.jpg (most confident frame, annotated), /tmp/smoke_last.jpg (latest raw frame)."""
import argparse, os, sys, time
import cv2
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('--source', default='http://%s:5000/video_feed' % os.environ.get('PINKY_IP', '192.168.4.1'))
ap.add_argument('--model', default=os.path.join(ROOT, 'smoke', 'models', 'rabahdev', 'best.pt'))
ap.add_argument('--seconds', type=float, default=120)
ap.add_argument('--conf', type=float, default=0.10, help='report threshold (low, to see weak detections)')
ap.add_argument('--alarm-conf', type=float, default=0.40, help='threshold the real alarm uses')
a = ap.parse_args()
from ultralytics import YOLO
m = YOLO(a.model); names = m.names
cap = cv2.VideoCapture(a.source)
if not cap.isOpened(): sys.exit('cannot open ' + a.source)
t0 = tl = time.time(); n = 0; mx = {}; hits = 0; best = 0.0; total = {'frames': 0, 'alarm_frames': 0}
while time.time() - t0 < a.seconds:
    ok, f = cap.read()
    if not ok: time.sleep(0.05); continue
    r = m.predict(f, conf=a.conf, imgsz=640, device='cpu', verbose=False)[0]
    n += 1; total['frames'] += 1; ab = False
    for b in r.boxes:
        nm = names[int(b.cls)]; c = float(b.conf); mx[nm] = max(mx.get(nm, 0), c)
        if nm == 'smoke' and c >= a.alarm_conf: ab = True
        if nm == 'smoke' and c > best:
            best = c; cv2.imwrite('/tmp/smoke_best.jpg', r.plot())
    hits += ab; total['alarm_frames'] += ab
    if n % 5 == 0: cv2.imwrite('/tmp/smoke_last.jpg', r.plot())
    if time.time() - tl >= 2:
        print('t=%3.0fs frames=%d  max conf: %s  frames>=%.2f: %d' % (time.time() - t0, n, {k: round(v, 2) for k, v in mx.items()} or '-', a.alarm_conf, hits), flush=True)
        tl = time.time(); n = 0; mx = {}; hits = 0
print('DONE frames=%d frames_over_alarm_conf=%d best_smoke_conf=%.2f' % (total['frames'], total['alarm_frames'], best))
