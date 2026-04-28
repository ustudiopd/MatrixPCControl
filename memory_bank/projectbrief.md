# 프로젝트 브리프

## 목적

**A1616HD** 16×16 HDMI 매트릭스 스위처를 제어 PC에서 **로컬**로 안정적으로 조작한다.

- 통신: **RS-232 Serial** (pyserial)
- 앱: **FastAPI** 로컬 서버 + **브라우저 UI**
- 상세 요구·API·데이터 스키마·인수 기준: **`memory_bank/SPEC_A1616HD.md`**

## 성공 기준

- 명세 **§15 인수 기준 23항** 충족 (브라우저 제어, Serial 설정·연결 테스트, Status 기반 16출력 표시, I/O 이름, 수동 라우팅·프리셋·히스토리·되돌리기, Queue 단일 실행, atomic JSON, 로그 회전, Mock 드라이버 테스트).

## 범위

- 포함: 로컬 PC에서의 매트릭스 제어, 프리셋·Undo, JSON 영속, PyInstaller 배포(`A1616HD-Control.exe`).
- 단일 진실: 구현 세부는 항상 `SPEC_A1616HD.md`와 대조한다.
