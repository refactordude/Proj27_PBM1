"""DB 어댑터 타입 → 구현 클래스 매핑.

신규 DB 추가 방법:
1. app/adapters/db/<db>.py 에 DBAdapter 상속 클래스 작성
2. 아래 _REGISTRY에 추가
"""
from __future__ import annotations

from app.adapters.db.base import DBAdapter
from app.adapters.db.mysql import MySQLAdapter
from app.core.config import DatabaseConfig

_REGISTRY: dict[str, type[DBAdapter]] = {
    "mysql": MySQLAdapter,
    # "postgres": PostgresAdapter,  # 확장 예시
}


def supported_types() -> list[str]:
    return sorted(_REGISTRY.keys())


def build_adapter(config: DatabaseConfig) -> DBAdapter:
    cls = _REGISTRY.get(config.type)
    if cls is None:
        raise ValueError(
            f"지원하지 않는 DB 타입입니다: {config.type}. "
            f"adapters/db/registry.py에 등록 필요."
        )
    return cls(config)
