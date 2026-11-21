# 연기 감지 (smoke detector)

- `smoke_detector.py` — 웹캠/MJPEG/영상 + YOLO 연기 감지 모듈 (10프레임 중 5프레임 이상 감지 시 ALARM, 5초간 없으면 CLEAR).
- 사용처: `tools/smoke_response.py` (연기 감지 → LED 사이렌 + 안전지대 이동).
- 설치: `bash smoke/setup.sh` (저장소 루트에 `.venv` 생성).

## 모델 가중치는 저장소에 없습니다
`models/rabahdev/best.pt` (약 6 MB, YOLOv8n, 클래스 `smoke`, `fire`)는 출처/라이선스를 확인하지 못해 공개 저장소에 올리지 않았습니다(`.gitignore`).
팀 공유 폴더/USB로 받아 `smoke/models/rabahdev/best.pt` 에 두세요. 확인용 SHA-256 앞 16자리: `b91633799ceb052c`.

## 확인된 것 / 아닌 것
- ✅ 모델 로드, 클래스 이름 `smoke` 존재, CPU 약 34 ms/프레임.
- ⚠ **실제 연기 영상으로 정확도는 검증하지 못했습니다.** 현장에서 연기(또는 모니터에 연기 영상)를 보여 주고 `--show` 로 확인하고, 오탐/미탐이 있으면 `--conf`(기본 0.4), `--min-hits`(기본 5)를 조정하세요. 수증기·조명에 오탐 가능.
- 불꽃(`fire`)도 감지하려면 `--classes smoke,fire`.
