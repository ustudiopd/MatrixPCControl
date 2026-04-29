# 현재 작업 맥락

## 포커스

- **기능·구현 중심 명세**가 `memory_bank/SPEC_A1616HD.md` 및 관련 메모리뱅크 파일에 반영됨.
- 제품 정의: **A1616HD 16×16** 로컬 제어 (FastAPI + Serial + 브라우저 UI).
- **실장비 확인:** 라우팅 명령은 `{input}X{output}.` 형식(예 `1X1.`)으로 동작함 → `config`의 `route_template`, `POST /api/routing`, UI 수동 라우팅과 연동.
- **라우팅 응답:** 성공 응답 raw에 `Ch:0,V:01` … `Ch:15,V:xx`(16채널)가 오면 `routing_parse`로 전체 `state.outputs` 갱신. 없으면 기존처럼 해당 output 한 칸만 갱신.
- **제거됨:** `Status.` / `%Version;` 및 `status_parse` / 상태 새로고침.
- **연결 테스트:** `probe_command`(기본 `.`) + `GET|POST /api/connection/test` 로 복구 — POST 시 `state.connected` 반영.

## 다음 단계 (명세 §12)

- **2단계(일부 완료):** 수동 라우팅 + **`data/history.json`**(최대 50) + **`data/undo_stack.json`**(최대 20) + `GET /api/history`, `GET /api/undo`, `POST /api/undo/{action_id}` + UI(최근 작업·되돌리기). 연결 테스트 성공/실패도 history에 기록.
- **남음(명세 순):** SerialCommandQueue/MatrixService 계층, 프리셋, 이름 UI, undo 상호 undo 등.

구현 시 세부는 항상 **`SPEC_A1616HD.md`**와 대조한다.
