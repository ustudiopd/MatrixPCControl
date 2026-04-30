"""배포용 EXE 엔트리 — `python -m app.main` 과 동일하게 서버를 띄웁니다."""

from __future__ import annotations


def main() -> None:
    from app.main import main as run_server

    run_server()


if __name__ == "__main__":
    main()
