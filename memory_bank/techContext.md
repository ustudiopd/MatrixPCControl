# 기술 맥락

## 스택

- **Python** — 앱 진입: `python app/main.py` (명세 §14)
- **FastAPI** — 로컬 REST API (`/api/...`, 명세 §7)
- **pyserial** — COM(RS-232)
- **정적 브라우저 UI** — FastAPI에서 서빙
- **배포**: PyInstaller → `A1616HD-Control.exe`

## 환경

- OS: **Windows** (COM 포트 전제)
- 저장소: `MatrixPCControl`
- 데이터 디렉터리: `data/` — `config.json`, `state.json`, `presets.json`, `history.json`, `undo_stack.json`, `logs/app.log`

## 설정 기본값 (Serial)

- `COM3`, 9600, 8N1, timeout 0.5 — 상세는 `SPEC_A1616HD.md` §4.1, §8.2

## 제약

- 장비 명령은 **SerialCommandQueue**로 **한 번에 하나**만 실행.
- JSON 저장은 **atomic write** (명세 §9).
- 로그: 약 **10MB**, **5파일** 회전 (§10).
- history 최대 **50**, undo_stack 최대 **20** (§4.9, §4.10).

## 프로토콜 프로파일

- `A1616HD_SERIAL_DOT` — `Status.`, `%Version;`, `{in}X{out}.` 등 (명세 §5)
