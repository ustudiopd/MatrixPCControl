# 시스템 패턴

## 아키텍처 (데이터 흐름)

```text
브라우저 UI → FastAPI → MatrixService → SerialCommandQueue → MatrixSerialDriver → pyserial → A1616HD
```

동시에 **JSON 저장소**(`data/`)에 설정·상태·프리셋·히스토리·Undo를 둔다.

## 핵심 패턴

| 패턴 | 설명 |
|------|------|
| 단일 Serial 경로 | 모든 장비 I/O는 Queue를 통해서만 |
| 작업 중 UI 락 | Queue `running` 시 주요 버튼 비활성 |
| 액션 후 검증 | 라우팅·프리셋·되돌리기 성공 후 `Status.` 재조회 |
| Undo 스냅샷 | 변경된 **Output만** before/after 저장 (전체 16×16 전체 스냅샷 아님) |
| 파싱 안전 | `Status.` 파싱 실패 시 기존 `state` 무단 덮어쓰기 금지 |
| 무장비 개발 | **MockSerialDriver**로 1단계·테스트 병행 |

## 관례

- Plan / Act: `AGENTS.md`, `.cursor/rules`
- 구현·API·스키마: **`memory_bank/SPEC_A1616HD.md`**

## 주요 모듈 책임 (명세 §2.2)

- **MatrixService**: 라우팅, 프리셋, 되돌리기, 상태 갱신
- **SerialCommandQueue**: 순차 실행, 새로고침/연결 테스트 중복 억제
- **MatrixSerialDriver**: 바이트 수준 명령·응답·파싱
