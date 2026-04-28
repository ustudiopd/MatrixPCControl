# 현재 작업 맥락

## 포커스

- **기능·구현 중심 명세**가 `memory_bank/SPEC_A1616HD.md` 및 관련 메모리뱅크 파일에 반영됨.
- 제품 정의: **A1616HD 16×16** 로컬 제어 (FastAPI + Serial + 브라우저 UI).
- **실장비 확인:** 라우팅 명령은 `{input}X{output}.` 형식(예 `1X1.`)으로 동작함 → `config`의 `route_template`, `POST /api/routing`, UI 수동 라우팅과 연동.
- **제거됨:** `Status.` / `%Version;` 및 `status_parse` / 상태 새로고침.
- **연결 테스트:** `probe_command`(기본 `.`) + `GET|POST /api/connection/test` 로 복구 — POST 시 `state.connected` 반영.

## 다음 단계 (명세 §12)

- **1단계** 우선: FastAPI 골격, 정적 UI, `config.json`, `MatrixSerialDriver` + **SerialCommandQueue**, 연결 테스트, `Status.`·파싱, Output 1~16 표시, **MockSerialDriver**.

구현 시 세부는 항상 **`SPEC_A1616HD.md`**와 대조한다.
