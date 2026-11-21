#!/usr/bin/env python3
"""Smoke -> evacuation guide demo.

  robot camera (MJPEG) -> YOLO smoke detector (laptop) -> ALARM
      -> LED siren (red/blue alternating, "뻐용뻐용") + drive to the safe zone with Nav2
      -> at the safe zone: solid green until reset

Run (needs: robot up via pinky_up.sh, camera_server + led_server on the robot, Nav2 active):
    .venv/bin/python tools/smoke_response.py                       # real robot
    .venv/bin/python tools/smoke_response.py --source 0            # laptop webcam as camera
    .venv/bin/python tools/smoke_response.py --source smoke.mp4 --dry-run   # no robot at all

Manual control while running (ROS topic /pinky/smoke, std_msgs/String):
    ros2 topic pub --once /pinky/smoke std_msgs/msg/String "{data: 'trigger'}"   # fake smoke
    ros2 topic pub --once /pinky/smoke std_msgs/msg/String "{data: 'reset'}"     # back to idle (LED off)
"""
import argparse
import logging
import os
import signal
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'smoke'))

log = logging.getLogger('evac')

RED, BLUE, GREEN, OFF = (255, 0, 0), (0, 0, 255), (0, 255, 0), None


# --------------------------------------------------------------------------- logic (no ROS needed)
class Siren:
    """alternates the LED ring red / blue until stop()"""

    def __init__(self, led, period=0.4):
        self.led, self.period = led, period
        self._stop = threading.Event()
        self._t = None

    def start(self):
        if self._t and self._t.is_alive():
            return
        self._stop.clear()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self):
        i = 0
        while not self._stop.is_set():
            self.led.fill(RED if i % 2 == 0 else BLUE)
            i += 1
            self._stop.wait(self.period)

    def stop(self):
        self._stop.set()
        if self._t:
            self._t.join(timeout=2)


class Evacuator:
    """IDLE --alarm--> EVACUATING --arrived--> ARRIVED ; failure -> FAILED (siren keeps running)
    reset() returns to IDLE.  `nav.goto(x, y, yaw)` must block and return True on arrival."""
    IDLE, EVACUATING, ARRIVED, FAILED = 'IDLE', 'EVACUATING', 'ARRIVED', 'FAILED'

    def __init__(self, nav, led, safe=(1.2, 1.2, 0.0), retries=2, period=0.4):
        self.nav, self.led, self.safe, self.retries = nav, led, safe, retries
        self.siren = Siren(led, period)
        self.state = self.IDLE
        self._lock = threading.Lock()
        self._worker = None

    def alarm(self, ev=None):
        with self._lock:
            if self.state != self.IDLE:
                log.info('alarm ignored (state=%s)', self.state)
                return False
            self.state = self.EVACUATING
        log.warning('SMOKE ALARM -> siren on, heading to safe zone %s', self.safe[:2])
        self.siren.start()
        self._worker = threading.Thread(target=self._go, daemon=True)
        self._worker.start()
        return True

    def _go(self):
        ok = False
        for attempt in range(1, self.retries + 2):
            try:
                ok = self.nav.goto(*self.safe)
            except Exception:
                log.exception('goto failed')
                ok = False
            if ok:
                break
            log.warning('could not reach safe zone (attempt %d/%d)', attempt, self.retries + 1)
            time.sleep(1.0)
        with self._lock:
            if self.state != self.EVACUATING:      # reset() was called meanwhile
                return
            self.state = self.ARRIVED if ok else self.FAILED
        if ok:
            log.warning('ARRIVED at safe zone -> siren off, green')
            self.siren.stop()
            self.led.fill(GREEN)
        else:
            log.error('FAILED to reach safe zone; siren stays on. Check Nav2/map/safe-zone coordinates.')

    def reset(self):
        with self._lock:
            was = self.state
            self.state = self.IDLE
        try:
            self.nav.cancel()
        except Exception:
            pass
        self.siren.stop()
        self.led.clear()
        log.info('reset (was %s)', was)

    def close(self):
        self.reset()


# --------------------------------------------------------------------------- fakes for --dry-run / tests
class FakeNav:
    def __init__(self, ok=True, delay=2.0):
        self.ok, self.delay, self.cancelled = ok, delay, False

    def goto(self, x, y, yaw=0.0):
        log.info('[dry-run] goto (%.2f, %.2f)', x, y)
        time.sleep(self.delay)
        return self.ok

    def cancel(self):
        self.cancelled = True


class FakeLed:
    def __init__(self, quiet=False):
        self.calls, self.quiet = [], quiet

    def fill(self, color):
        self.calls.append(('fill', color))
        if not self.quiet:
            log.info('[dry-run] LED fill %s', {RED: 'RED', BLUE: 'BLUE', GREEN: 'GREEN'}.get(color, color))

    def clear(self):
        self.calls.append(('clear', None))
        if not self.quiet:
            log.info('[dry-run] LED clear')


# --------------------------------------------------------------------------- ROS glue
class RosLed:
    """/set_led (pinky_interfaces/SetLed, served by `ros2 run pinky_led led_server` on the robot)"""

    def __init__(self, node):
        from pinky_interfaces.srv import SetLed
        self.SetLed, self.node = SetLed, node
        self.cli = node.create_client(SetLed, 'set_led')
        self.ready = self.cli.wait_for_service(timeout_sec=5.0)
        if not self.ready:
            log.warning('/set_led service not available - run `ros2 run pinky_led led_server` on the robot (LED will not light)')

    def _call(self, command, color=(0, 0, 0)):
        if not self.cli.service_is_ready():
            return
        r = self.SetLed.Request()
        r.command, r.r, r.g, r.b = command, int(color[0]), int(color[1]), int(color[2])
        self.cli.call_async(r)

    def fill(self, color):
        self._call('fill', color)

    def clear(self):
        self._call('clear')


def check_safe_zone(node, x, y, timeout=5.0):
    """warn loudly if (x, y) is not a known-free cell of the current /map"""
    from nav_msgs.msg import OccupancyGrid
    from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
    box = {}
    node.create_subscription(OccupancyGrid, 'map', lambda m: box.setdefault('m', m),
                             QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL))
    t0 = time.time()
    while 'm' not in box and time.time() - t0 < timeout:
        time.sleep(0.1)
    m = box.get('m')
    if m is None:
        log.warning('no /map received - cannot verify the safe zone (is Nav2/map_server running?)')
        return None
    i = m.info
    c, r = int((x - i.origin.position.x) / i.resolution), int((y - i.origin.position.y) / i.resolution)
    if not (0 <= c < i.width and 0 <= r < i.height):
        log.error('SAFE ZONE (%.2f, %.2f) IS OUTSIDE THE MAP (map x[%.2f..%.2f] y[%.2f..%.2f]). The robot will not be able to go there.',
                  x, y, i.origin.position.x, i.origin.position.x + i.width * i.resolution,
                  i.origin.position.y, i.origin.position.y + i.height * i.resolution)
        return False
    v = m.data[r * i.width + c]
    if v != 0:
        log.error('SAFE ZONE (%.2f, %.2f) is not free in the map (cell value %d: -1 unknown, >0 obstacle).', x, y, v)
        return False
    log.info('safe zone (%.2f, %.2f) is a free cell in the map', x, y)
    return True


def main():
    ap = argparse.ArgumentParser(description='smoke -> siren + drive to safe zone', formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    ap.add_argument('--source', default='http://192.168.4.1:5000/video_feed', help='MJPEG URL, camera index, or video file')
    ap.add_argument('--model', default=os.path.join(ROOT, 'smoke', 'models', 'rabahdev', 'best.pt'))
    ap.add_argument('--classes', default='smoke')
    ap.add_argument('--conf', type=float, default=0.4)
    ap.add_argument('--min-hits', type=int, default=5)
    ap.add_argument('--window', type=int, default=10)
    ap.add_argument('--device', default='cpu', help='cpu or 0 (GPU)')
    ap.add_argument('--safe-x', type=float, default=1.2, help='safe zone x in map frame [m]')
    ap.add_argument('--safe-y', type=float, default=1.2, help='safe zone y in map frame [m]')
    ap.add_argument('--safe-yaw', type=float, default=0.0)
    ap.add_argument('--siren-period', type=float, default=0.4, help='seconds per colour')
    ap.add_argument('--snapshots', default=os.path.join(ROOT, 'smoke', 'snapshots'))
    ap.add_argument('--show', action='store_true', help='preview window')
    ap.add_argument('--dry-run', action='store_true', help='no ROS/robot: only log what would happen')
    ap.add_argument('--no-detector', action='store_true', help='skip YOLO; only listen to /pinky/smoke commands')
    a = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    safe = (a.safe_x, a.safe_y, a.safe_yaw)

    node = None
    if a.dry_run:
        evac = Evacuator(FakeNav(), FakeLed(), safe, period=a.siren_period)
    else:
        from pinky_nav import PinkyNav
        nav = PinkyNav()
        node = nav
        evac = Evacuator(nav, RosLed(nav), safe, period=a.siren_period)
        check_safe_zone(nav, a.safe_x, a.safe_y)
        from std_msgs.msg import String

        def cmd(m):
            c = m.data.strip().lower()
            log.info('command: %s', c)
            if c == 'trigger':
                evac.alarm({'event': 'MANUAL'})
            elif c == 'reset':
                evac.reset()
        nav.create_subscription(String, '/pinky/smoke', cmd, 10)

    det = None
    if not a.no_detector:
        from smoke_detector import SmokeDetector, setup_logging
        setup_logging(os.path.join(ROOT, 'smoke', 'smoke.log'))
        logging.getLogger('smoke').propagate = False   # avoid duplicate lines (own handler + root)
        src = int(a.source) if str(a.source).isdigit() else a.source
        det = SmokeDetector(a.model, camera=src, conf=a.conf, device=a.device, smoke_names=tuple(a.classes.split(',')),
                            window=a.window, min_hits=a.min_hits, snapshot_dir=a.snapshots,
                            on_alarm=evac.alarm)
        log.info('model classes: %s', det.model.names)
        names = {str(n).lower() for n in det.model.names.values()}
        if not (names & det.smoke_names):
            log.error('none of --classes %s found in model classes %s -> smoke will never be detected!', sorted(det.smoke_names), sorted(names))

    def _term(*_):
        raise KeyboardInterrupt      # rclpy swallows SIGTERM; make `kill <pid>` (pinky_down.sh) stop us cleanly
    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)

    try:
        if det is not None and a.show:
            det.run(show=True)            # main thread (preview window)
        else:
            if det is not None:
                det.start()
            log.info('running. Ctrl-C to stop.%s', '' if det else ' (no detector; use /pinky/smoke commands)')
            while True:
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        if det is not None:
            det.stop()
        evac.close()
        if node is not None:
            time.sleep(0.3)           # let the last LED 'clear' request go out
            node.close()


if __name__ == '__main__':
    main()
