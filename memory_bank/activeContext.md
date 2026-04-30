# 현재 작업 맥락

## 포커스

- **기능·구현 중심 명세**가 `memory_bank/SPEC_A1616HD.md` 및 관련 메모리뱅크 파일에 반영됨.
- 제품 정의: **A1616HD 16×16** 로컬 제어 (FastAPI + Serial + 브라우저 UI).
- **실장비 확인:** 라우팅 명령은 `{input}X{output}.` 형식(예 `1X1.`)으로 동작함 → `config`의 `route_template`, `POST /api/routing`, UI 수동 라우팅과 연동.
- **라우팅 응답:** 성공 응답 raw에 `Ch:0,V:01` … `Ch:15,V:xx`(16채널)가 오면 `routing_parse`로 전체 `state.outputs` 갱신. 없으면 기존처럼 해당 output 한 칸만 갱신.
- **제거됨:** `Status.` / `%Version;` 및 `status_parse` / 상태 새로고침.
- **연결 테스트:** `probe_command`(기본 `.`) + `GET|POST /api/connection/test` 로 복구 — POST 시 `state.connected` 반영.

## 다음 단계 (명세 §12)

- **3단계(완료): 이름 관리** — `config.json`의 `inputs`/`outputs`(`no`, `name`), `GET /api/settings`·`PUT|POST /api/settings/io-names`, UI 표 16+16 저장, `/api/status` 응답에 `output_display`/`input_display`로 이름 반영; 수동 라우팅에 선택 채널 이름 미리보기.
- **4단계(완료): 프리셋 전부** — CRUD·순서·실행, 라우트 사이 **`presets.route_between_sec`** 저장(명세 100–200ms, `PUT /api/settings/presets-timing`), 성공 시 history·undo·중단 시 기록. `GET /api/presets/{id}` 단건. **§7:** `GET /api/connection` (state 요약).
- **2·5단계 등:** 수동 라우팅·history·undo UI는 이미 병행 구현됨.
- **6단계(완료): 안정화** — `data/logs/app.log` **10MB·5파일 회전**, 주요 API에 파일 로그, Serial은 기존처럼 `with`로 포트 닫힘; UI **재진입 플래그**(`__matrixControlInflight`); JSON은 기존 `atomic_write_json`; 배포: `A1616HD-Control.spec` / `dist/A1616HD-Control.exe`, `entry.py`, EXE 옆 `data/`; 장비 없이 `device.transport: "mock"` 또는 `MATRIXPC_MOCK_TRANSPORT=1`.

구현 시 세부는 항상 **`SPEC_A1616HD.md`**와 대조한다.
