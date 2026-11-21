"""웹캠 + YOLO 연기 감지 모듈.

단독 실행:  python smoke_detector.py --model smoke.pt --show
모듈 사용:
    from smoke_detector import SmokeDetector
    det = SmokeDetector("smoke.pt", on_alarm=lambda ev: print(ev))
    det.start()      # 백그라운드 스레드로 실행
    ...
    det.stop()
"""
import argparse
import logging
import threading
import time
from collections import deque
from logging.handlers import RotatingFileHandler

import cv2

log = logging.getLogger("smoke")


def setup_logging(path="smoke.log", level=logging.INFO):
    log.setLevel(level)
    if log.handlers:
        return
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    for h in (logging.StreamHandler(),
              RotatingFileHandler(path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)


class SmokeDetector:
    """연기 감지기.

    오탐 방지: 최근 `window`프레임 중 `min_hits`프레임 이상에서 연기가 보이면 ALARM,
    `clear_sec`초 동안 연기가 없으면 CLEAR. (붕어빵 수증기 오탐 시 conf/min_hits 올릴 것)
    on_alarm / on_clear 콜백은 dict(event 정보)를 받는다 -> 붕어빵 앱의 알람 UI에 연결.
    """

    def __init__(self, model_path, camera=0, conf=0.4, imgsz=640, device=None,
                 smoke_names=("smoke",), window=10, min_hits=5, clear_sec=5.0,
                 on_alarm=None, on_clear=None, on_frame=None,
                 width=1280, height=720, snapshot_dir=None):
        from ultralytics import YOLO  # 지연 import: 모듈 로드만으로 torch를 끌어오지 않음
        self.model = YOLO(model_path)
        self.camera, self.conf, self.imgsz, self.device = camera, conf, imgsz, device
        self.smoke_names = {s.lower() for s in smoke_names}
        self.hits = deque(maxlen=window)
        self.min_hits, self.clear_sec = min_hits, clear_sec
        self.on_alarm, self.on_clear, self.on_frame = on_alarm, on_clear, on_frame
        self.width, self.height = width, height
        self.snapshot_dir = snapshot_dir
        self.alarm_active = False
        self._last_smoke_t = 0.0
        self._stop = threading.Event()
        self._thread = None

    # ---- 단일 프레임 처리 (BGR ndarray). 웹캠 대신 다른 소스 프레임을 넣어도 됨 ----
    def process_frame(self, frame):
        r = self.model.predict(frame, conf=self.conf, imgsz=self.imgsz,
                               device=self.device, verbose=False)[0]
        dets = []
        for b in r.boxes:
            name = r.names[int(b.cls)].lower()
            if name in self.smoke_names:
                dets.append({"conf": float(b.conf), "box": [int(v) for v in b.xyxy[0]]})
        now = time.time()
        self.hits.append(bool(dets))
        if dets:
            self._last_smoke_t = now

        if not self.alarm_active and sum(self.hits) >= self.min_hits:
            self.alarm_active = True
            ev = {"event": "ALARM", "time": now, "detections": dets}
            log.warning("SMOKE DETECTED conf=%.2f boxes=%s",
                        max(d["conf"] for d in dets), [d["box"] for d in dets])
            if self.snapshot_dir:
                self._snapshot(r.plot(), now)
            if self.on_alarm:
                self._safe(self.on_alarm, ev)
        elif self.alarm_active and now - self._last_smoke_t > self.clear_sec:
            self.alarm_active = False
            self.hits.clear()
            log.info("SMOKE CLEARED")
            if self.on_clear:
                self._safe(self.on_clear, {"event": "CLEAR", "time": now})
        return dets, r

    def _snapshot(self, img, t):
        import os
        os.makedirs(self.snapshot_dir, exist_ok=True)
        p = os.path.join(self.snapshot_dir, time.strftime("smoke_%Y%m%d_%H%M%S.jpg", time.localtime(t)))
        cv2.imwrite(p, img)
        log.info("snapshot saved: %s", p)

    @staticmethod
    def _safe(fn, ev):
        try:
            fn(ev)
        except Exception:
            log.exception("callback error")

    # ---- 메인 루프 ----
    def run(self, show=False):
        cap = cv2.VideoCapture(self.camera)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        if not cap.isOpened():
            log.error("웹캠을 열 수 없음: %s", self.camera)
            return
        log.info("started (camera=%s)", self.camera)
        fails = 0
        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    fails += 1
                    if fails > 30:
                        log.error("프레임 읽기 반복 실패, 카메라 재연결 시도")
                        cap.release(); time.sleep(2)
                        cap = cv2.VideoCapture(self.camera); fails = 0
                    time.sleep(0.05)
                    continue
                fails = 0
                dets, r = self.process_frame(frame)
                if self.on_frame:
                    self._safe(self.on_frame, {"frame": frame, "detections": dets})
                if show:
                    img = r.plot()
                    if self.alarm_active:
                        cv2.putText(img, "SMOKE ALARM", (20, 50), cv2.FONT_HERSHEY_SIMPLEX,
                                    1.5, (0, 0, 255), 4)
                    cv2.imshow("smoke", img)
                    if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                        break
        finally:
            cap.release()
            if show:
                cv2.destroyAllWindows()
            log.info("stopped")

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)


def main():
    ap = argparse.ArgumentParser(description="웹캠 YOLO 연기 감지")
    ap.add_argument("--model", required=True, help="연기 학습된 YOLO 가중치(.pt)")
    ap.add_argument("--camera", default=0, help="카메라 인덱스 또는 영상 경로/RTSP")
    ap.add_argument("--conf", type=float, default=0.4)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default=None, help="예: cpu, 0")
    ap.add_argument("--classes", default="smoke", help="연기로 간주할 클래스명(쉼표 구분)")
    ap.add_argument("--min-hits", type=int, default=5)
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--clear-sec", type=float, default=5.0)
    ap.add_argument("--log", default="smoke.log")
    ap.add_argument("--snapshots", default=None, help="알람 시 이미지 저장 폴더")
    ap.add_argument("--show", action="store_true", help="미리보기 창 (q/ESC 종료)")
    a = ap.parse_args()
    setup_logging(a.log)
    cam = int(a.camera) if str(a.camera).isdigit() else a.camera
    det = SmokeDetector(a.model, camera=cam, conf=a.conf, imgsz=a.imgsz, device=a.device,
                        smoke_names=tuple(a.classes.split(",")), window=a.window,
                        min_hits=a.min_hits, clear_sec=a.clear_sec, snapshot_dir=a.snapshots)
    try:
        det.run(show=a.show)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
