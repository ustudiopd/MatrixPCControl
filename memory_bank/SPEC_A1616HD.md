# A1616HD 매트릭스 PC 제어 프로그램

# 기능·구현 중심 명세서

- 구현 방향: **PC 로컬 실행 / RS-232 Serial 제어 / FastAPI / 로컬 브라우저 UI**
- 대상 장비: **A1616HD Matrix Switcher 16x16**

---

## 1. 프로젝트 개요

로컬 제어 프로그램. 사용자는 브라우저에서: 장비 연결 확인, Output별 Input 상태, I/O 이름 관리, 수동 라우팅, 프리셋 CRUD·실행, 최근 작업·되돌리기, 설정 저장/불러오기.

장비와 **RS-232 Serial** 통신. 모든 장비 명령은 **단일 실행 경로**에서 순차 처리.

---

## 2. 전체 구현 구조

### 2.1 시스템 구조

`브라우저 UI → FastAPI → MatrixService → SerialCommandQueue → MatrixSerialDriver → pyserial → RS-232 → A1616HD`

### 2.2 계층 역할

| 계층 | 역할 |
|------|------|
| 브라우저 UI | 상태·라우팅·프리셋·되돌리기 |
| FastAPI | 로컬 API |
| MatrixService | 라우팅·프리셋·되돌리기·상태 갱신 |
| SerialCommandQueue | Serial 명령 순차 처리 |
| MatrixSerialDriver | 명령 생성·전송·수신·파싱 |
| pyserial | COM 포트 |
| JSON 저장소 | 설정·상태·프리셋·히스토리·Undo |

---

## 3. 실행 흐름

### 3.1 프로그램 시작

1. 실행 → `data` 확인 → `config.json` / `presets.json` / `history.json` / `undo_stack.json` 로드 → `MatrixSerialDriver` 초기화 → FastAPI 기동 → 기본 브라우저로 제어 화면 → 사용자 연결 테스트 또는 상태 새로고침.

### 3.2 기본 화면

표시: 저장된 COM·baudrate, 마지막 연결 결과·상태 시각, Output 1~16 라우팅, I/O 이름, 프리셋 목록, 최근 작업. 초기에는 저장값 우선, 연결 테스트/새로고침 시 장비 반영.

---

## 4. 주요 기능 명세 (요약)

### 4.1 장비 연결 설정

- 항목: COM, baudrate, bytesize, parity, stopbits, timeout.
- 기본값: port `COM3`, 9600, 8, `N`, 1, timeout 0.5.
- 저장: `data/config.json`. 변경 시 기존 Serial close 후 재연결.

### 4.2 연결 테스트

- 명령: `Status.` (보조 `%Version;`).
- 흐름: UI → `MatrixService.test_connection()` → Queue → Driver open → 전송 → 응답 확인 → `state.json`·`history.json` → UI.
- 성공: open·전송·timeout 내 응답. 실패: open 실패·무응답·timeout·파싱 실패.

### 4.3 라우팅 상태 확인

- 명령: `Status.`
- `get_routing_status()`: 버퍼 정리 → 전송 → 수신 → Output별 Input 파싱 → 내부 상태 → `state.json`.

### 4.4 상태 새로고침

- `refresh_status()`: 버튼 비활성 → Queue로 `Status.` → 파싱 → `state.json` → history → UI → 활성화.
- 트리거: 사용자 클릭, 연결 테스트 후, 수동 라우팅·프리셋·되돌리기 성공 후.
- 라우팅/프리셋/되돌리기 **실행 중** 사용자 새로고침 중복 금지.

### 4.5 I/O 이름

- `config.json`의 `inputs`/`outputs`: `{ "no", "name" }`. 빈 이름은 번호만 표시.

### 4.6 수동 라우팅

- 명령: `{input_no}X{output_no}.`
- 흐름: 기존 Output 상태 저장 → Queue → `route()` → 성공 시 `Status.` 재조회 → state·history → **undo_stack** (변경 Output만 before/after).
- history 예: `manual_route`, `undoable`, id·title·success·created_at.

### 4.7~4.8 프리셋

- 필드: id, name, description, confirm_before_run, routes[], sort_order.
- 실행: 확인창(옵션) → 변경 Output들 이전 상태 저장 → Queue → routes 순차 + 100~200ms delay → **중간 실패 시 중단(기본)** → 완료 후 `Status.` → state·history·undo_stack.

### 4.9 최근 작업

- `history.json`, 최대 **50**건, 초과 시 오래된 것 삭제.
- 기록: 연결 테스트, 상태 새로고침, 수동 라우팅, 프리셋 실행, 되돌리기.

### 4.10 되돌리기

- 최근 작업에서 선택. 대상: 수동 라우팅·프리셋·되돌리기 **성공** 작업.
- `undo_stack`에서 action_id → before_routes → 확인창 → Queue로 before 복원 → `Status.` → history·undo_stack 갱신.
- **전체 16x16 저장 아님**, 변경 Output만. undo_stack 최대 **20**건.

---

## 5. Serial 통신

- 프로파일: `A1616HD_SERIAL_DOT`
- 명령: 상태 `Status.`, 버전 `%Version;`, 라우팅 `{in}v{out}.`(설정 `route_template`), `{in}All.`, `Save{n}.`, `Recall{n}.`
- Driver 메서드: `open/close/reconnect`, `test_connection`, `get_version`, `get_routing_status`, `get_signal_status`, `route`, `route_many`, `send_command`, `parse_status_response`
- `send_command`: 포트 확인 → in/out 버퍼 초기화 → encode → write → flush → timeout까지 읽기 → decode → 길이 제한 → 반환.
- `route_many`: 순차 + delay, 실패 시 중단, 결과 목록 반환.
- `Status.` 파싱: 예 `Ch:0,V:01` 형태 — **Ch 0-base ↔ UI 1~16 매핑**, V hex 등 변환 규칙 적용, **파싱 실패 시 기존 state 임의 덮어쓰기 금지**.

---

## 6. SerialCommandQueue

- 목적: 동시 명령 방지, 단일 순차 실행.
- 정책: 라우팅·프리셋·되돌리기 순차; **상태 새로고침·연결 테스트는 작업 중 중복 불가**.
- 상태: idle / running / failed. running 시: 연결 테스트·새로고침·라우팅·프리셋·되돌리기 UI 비활성.

---

## 7. FastAPI API

| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/connection` | 연결 상태 |
| POST | `/api/connection/test` | 연결 테스트 |
| POST | `/api/connection/reconnect` | 재연결 |
| GET | `/api/status` | 저장 상태 |
| POST | `/api/status/refresh` | 새로고침 |
| POST | `/api/routing` | 수동 라우팅 body `{input_no, output_no}` |
| GET | `/api/presets` | 목록 |
| POST | `/api/presets` | 생성 |
| PUT | `/api/presets/{preset_id}` | 수정 |
| DELETE | `/api/presets/{preset_id}` | 삭제 |
| PUT | `/api/presets/order` | 순서 |
| POST | `/api/presets/{preset_id}/run` | 실행 |
| GET | `/api/history` | 최근 작업 |
| GET | `/api/undo` | 되돌리기 가능 목록 |
| POST | `/api/undo/{action_id}` | 되돌리기 |
| GET | `/api/settings` | 전체 설정 |
| PUT | `/api/settings/serial` | Serial |
| PUT | `/api/settings/io-names` | I/O 이름 |

---

## 8. 데이터 저장

### 8.1 폴더 구조

```text
data/
 ├─ config.json
 ├─ state.json
 ├─ presets.json
 ├─ history.json
 ├─ undo_stack.json
 └─ logs/
     └─ app.log
```

### 8.2 config.json (예시)

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 8000,
    "auto_open_browser": true
  },
  "device": {
    "transport": "serial",
    "serial": {
      "port": "COM3",
      "baudrate": 9600,
      "bytesize": 8,
      "parity": "N",
      "stopbits": 1,
      "timeout": 0.5
    },
    "protocol": {
      "name": "A1616HD_SERIAL_DOT",
      "status_command": "Status.",
      "version_command": "%Version;",
      "route_template": "{input}v{output}."
    }
  },
  "status": {
    "refresh_after_action": true,
    "periodic_refresh_enabled": false
  },
  "history": {
    "max_items": 50
  },
  "undo": {
    "max_items": 20
  },
  "inputs": [
    { "no": 1, "name": "발표자 노트북" },
    { "no": 2, "name": "영상 재생 PC" }
  ],
  "outputs": [
    { "no": 1, "name": "LED 메인" },
    { "no": 2, "name": "연사자 모니터" }
  ]
}
```

### 8.3 state.json (예시)

```json
{
  "connected": true,
  "last_checked_at": "2026-04-24T14:30:00+09:00",
  "outputs": [
    { "output_no": 1, "input_no": 2 },
    { "output_no": 2, "input_no": 1 }
  ],
  "last_error": null
}
```

### 8.4 presets.json (예시)

```json
[
  {
    "id": "preset_001",
    "name": "발표자 노트북 → LED 메인",
    "description": "발표자 노트북을 LED 메인으로 출력합니다.",
    "confirm_before_run": false,
    "routes": [
      { "input_no": 1, "output_no": 1 }
    ],
    "sort_order": 1
  }
]
```

### 8.5 history.json (예시)

```json
[
  {
    "id": "action_20260424_143000_001",
    "type": "manual_route",
    "title": "영상 재생 PC → LED 메인",
    "success": true,
    "undoable": true,
    "created_at": "2026-04-24T14:30:00+09:00"
  }
]
```

### 8.6 undo_stack.json (예시)

```json
[
  {
    "action_id": "action_20260424_143000_001",
    "title": "영상 재생 PC → LED 메인",
    "before_routes": [
      { "output_no": 1, "input_no": 3 }
    ],
    "after_routes": [
      { "output_no": 1, "input_no": 2 }
    ],
    "created_at": "2026-04-24T14:30:00+09:00"
  }
]
```

### 8.7 라우팅 API 응답 예시

요청 `POST /api/routing`:

```json
{ "input_no": 2, "output_no": 1 }
```

응답:

```json
{
  "success": true,
  "message": "연결 완료",
  "route": { "input_no": 2, "output_no": 1 }
}
```

---

## 9. 저장 안정성

**Atomic write**: 임시 파일 쓰기 → 완료 확인 → rename/replace → 실패 시 기존 유지. 대상: 위 JSON 전부.

---

## 10. 로그

- `data/logs/app.log`
- 항목: 시작, Serial 시도, 연결 테스트, Status., 라우팅·프리셋·되돌리기, 오류.
- **최대 10MB, 5파일 회전**.

---

## 11. 화면

영역: 연결 상태, Output/Input 상태, 수동 라우팅, 프리셋, 최근 작업·되돌리기, I/O 이름, Serial 설정, 간단 로그. 실행 중 버튼 비활성, 실패 메시지, 최신순, undoable만 버튼.

---

## 12. 개발 단계

1. Serial+상태: FastAPI, 정적 UI, config, Driver, Queue, 연결 테스트, Status., 파싱, 16출력 표시, **MockSerialDriver**
2. 수동 라우팅 + history + undo_stack
3. 이름 관리
4. 프리셋 전부
5. history UI + undo API + 복원
6. 안정화: close 보장, 로그 회전, atomic write, 중복 클릭 방지, PyInstaller → `A1616HD-Control.exe`

개발 실행: `python app/main.py`

---

## 13~14. 테스트·배포

- 테스트: 연결 성공/실패, baud, 재시도, Status 파싱·실패 시 덮어쓰기 방지, 새로고침 중복 무시, 라우팅·프리셋·undo, JSON 한도·atomic.
- 배포 폴더: exe + `data/` + logs.

---

## 15. 인수 기준 (23항)

1. 프로그램 실행 후 브라우저 제어 화면이 열린다.  
2. FastAPI 로컬 서버가 실행된다.  
3. Serial COM 포트를 설정할 수 있다.  
4. Baudrate를 설정할 수 있다.  
5. 연결 테스트를 실행할 수 있다.  
6. 장비 응답 여부를 확인할 수 있다.  
7. `Status.` 명령으로 Output 1~16 상태를 조회할 수 있다.  
8. Input / Output 이름을 수정할 수 있다.  
9. 수동 라우팅을 실행할 수 있다.  
10. 라우팅 후 상태가 자동 재조회된다.  
11. 프리셋을 생성 / 수정 / 삭제할 수 있다.  
12. 프리셋을 실행할 수 있다.  
13. 프리셋 실행 후 상태가 자동 재조회된다.  
14. 최근 작업 기록을 볼 수 있다.  
15. 수동 라우팅과 프리셋 실행을 되돌릴 수 있다.  
16. 되돌리기 후 상태가 자동 재조회된다.  
17. Serial 명령은 동시에 하나만 실행된다.  
18. 작업 중 버튼 중복 실행이 방지된다.  
19. history는 최대 50개로 유지된다.  
20. undo_stack은 최대 20개로 유지된다.  
21. JSON 파일은 atomic write로 저장된다.  
22. 로그 파일은 크기 제한과 회전 저장이 적용된다.  
23. 실제 장비 없이 MockSerialDriver로 주요 기능 테스트가 가능하다.

---

## 16. 구현 요약 원칙

1. UI와 Serial 로직 분리  
2. 장비 명령은 Driver에 집약  
3. 모든 Serial 명령은 Queue 단일 경로  
4. 라우팅·프리셋·되돌리기 후 `Status.` 재확인  
5. 작업·Undo는 JSON 영속  
6. JSON은 atomic write  
7. **MockSerialDriver**로 무장비 테스트

본 명세는 **현장 운영용 매트릭스 제어를 안정적으로 구현**하는 것을 기준으로 한다.
