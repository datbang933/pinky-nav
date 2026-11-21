#!/usr/bin/env python3
"""Pinky Pro camera -> MJPEG over HTTP.  Runs ON THE ROBOT (stdlib + OpenCV only, no ROS).

Why HTTP instead of a ROS image topic: over Wi-Fi a ROS image is split into many UDP
packets and one lost packet drops the whole frame; an HTTP/TCP stream just slows down.

    scp tools/camera_server.py pinky@192.168.4.1:~/
    python3 ~/camera_server.py                        # 640x480, 10 fps, port 5000
    python3 ~/camera_server.py --rotate 180           # if the picture is upside down
    python3 ~/camera_server.py --swap-rb              # if red/blue are swapped

Endpoints:  /video_feed (MJPEG)   /snapshot.jpg (latest frame)   /stats (JSON)

Camera backends tried in order: pinkylib.Camera, picamera2, OpenCV (/dev/video0).
Only one program can own the camera: stop Jupyter notebooks etc. that use it.
"""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

ROT = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}


def open_camera(width, height):
    errors = []
    try:
        from pinkylib import Camera
        cam = Camera()
        cam.start()
        return 'pinkylib', cam.get_frame, cam.close
    except Exception as e:
        errors.append(f'pinkylib: {e}')
    try:
        from picamera2 import Picamera2
        cam = Picamera2()
        cam.configure(cam.create_preview_configuration(main={'format': 'RGB888', 'size': (width, height)}))
        cam.start()
        return 'picamera2', cam.capture_array, lambda: (cam.stop(), cam.close())
    except Exception as e:
        errors.append(f'picamera2: {e}')
    try:
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if not cap.isOpened():
            raise RuntimeError('cannot open /dev/video0')
        return 'opencv', (lambda: cap.read()[1]), cap.release
    except Exception as e:
        errors.append(f'opencv: {e}')
    raise RuntimeError('no camera backend worked (is another program using the camera?): ' + '; '.join(errors))


class Latest:
    """newest JPEG + condition variable; every viewer gets the latest frame (slow viewers skip frames)"""
    def __init__(self):
        self.cond = threading.Condition()
        self.jpeg = None
        self.seq = 0
        self.fps = 0.0
        self.viewers = 0


def capture_loop(latest, read, a):
    period, n, t0 = 1.0 / a.fps, 0, time.time()
    while True:
        t = time.time()
        frame = read()
        if frame is not None:
            if a.swap_rb:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            if frame.shape[1] != a.width or frame.shape[0] != a.height:
                frame = cv2.resize(frame, (a.width, a.height))
            if a.rotate:
                frame = cv2.rotate(frame, ROT[a.rotate])
            ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, a.quality])
            if ok:
                with latest.cond:
                    latest.jpeg, latest.seq = buf.tobytes(), latest.seq + 1
                    latest.cond.notify_all()
                n += 1
                if time.time() - t0 >= 2:
                    latest.fps, n, t0 = n / (time.time() - t0), 0, time.time()
        time.sleep(max(0.0, period - (time.time() - t)))


def make_handler(latest):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path.startswith('/snapshot.jpg'):
                with latest.cond:
                    j = latest.jpeg
                if j is None:
                    self.send_error(503, 'no frame yet')
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(j)))
                self.end_headers()
                self.wfile.write(j)
            elif self.path.startswith('/stats'):
                b = json.dumps({'fps': round(latest.fps, 1), 'frames': latest.seq, 'viewers': latest.viewers}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(b)))
                self.end_headers()
                self.wfile.write(b)
            elif self.path.startswith('/video_feed'):
                self.send_response(200)
                self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                self.end_headers()
                latest.viewers += 1
                last = -1
                try:
                    while True:
                        with latest.cond:
                            latest.cond.wait_for(lambda: latest.seq != last, timeout=5)
                            j, last = latest.jpeg, latest.seq
                        if j is None:
                            continue
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(j))
                        self.wfile.write(j)
                        self.wfile.write(b'\r\n')
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    latest.viewers -= 1
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(b'<html><body><img src="/video_feed" style="max-width:100%"></body></html>')
    return H


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=5000)
    ap.add_argument('--width', type=int, default=640)
    ap.add_argument('--height', type=int, default=480)
    ap.add_argument('--fps', type=float, default=10)
    ap.add_argument('--quality', type=int, default=70)
    ap.add_argument('--rotate', type=int, default=0, choices=[0, 90, 180, 270])
    ap.add_argument('--swap-rb', action='store_true')
    a = ap.parse_args()
    name, read, close = open_camera(a.width, a.height)
    print(f'camera backend: {name}; serving http://0.0.0.0:{a.port}/video_feed', flush=True)
    latest = Latest()
    threading.Thread(target=capture_loop, args=(latest, read, a), daemon=True).start()
    try:
        ThreadingHTTPServer(('0.0.0.0', a.port), make_handler(latest)).serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        close()


if __name__ == '__main__':
    main()
